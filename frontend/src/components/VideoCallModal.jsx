import { useState, useEffect, useRef, useCallback } from "react";
import { io } from "socket.io-client";
import { api } from "../api";
import { useAuth } from "../context/AuthContext";

export default function VideoCallModal({ call, onClose }) {
  const { user } = useAuth();
  const [localStream, setLocalStream] = useState(null);
  const [peers, setPeers] = useState({}); // { sid: { user, stream, connection } }
  const [isMuted, setIsMuted] = useState(false);
  const [isVideoOff, setIsVideoOff] = useState(false);
  const [error, setError] = useState("");
  const [connecting, setConnecting] = useState(true);

  const localVideoRef = useRef(null);
  const socketRef = useRef(null);
  const peersRef = useRef({});
  const localStreamRef = useRef(null);

  const ICE_SERVERS = {
    iceServers: [
      { urls: "stun:stun.l.google.com:19302" },
      { urls: "stun:stun1.l.google.com:19302" },
    ],
  };

  const createPeerConnection = useCallback((remoteSid, isInitiator) => {
    const pc = new RTCPeerConnection(ICE_SERVERS);

    // Add local tracks
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => {
        pc.addTrack(track, localStreamRef.current);
      });
    }

    // Handle incoming tracks
    pc.ontrack = (event) => {
      setPeers((prev) => ({
        ...prev,
        [remoteSid]: {
          ...prev[remoteSid],
          stream: event.streams[0],
        },
      }));
    };

    // ICE candidates
    pc.onicecandidate = (event) => {
      if (event.candidate && socketRef.current) {
        socketRef.current.emit("ice-candidate", {
          target_sid: remoteSid,
          candidate: event.candidate,
        });
      }
    };

    pc.oniceconnectionstatechange = () => {
      if (pc.iceConnectionState === "disconnected" || pc.iceConnectionState === "failed") {
        // Clean up this peer
        setPeers((prev) => {
          const next = { ...prev };
          delete next[remoteSid];
          return next;
        });
      }
    };

    peersRef.current[remoteSid] = pc;

    if (isInitiator) {
      pc.createOffer()
        .then((offer) => pc.setLocalDescription(offer))
        .then(() => {
          socketRef.current?.emit("offer", {
            target_sid: remoteSid,
            offer: pc.localDescription,
          });
        })
        .catch(console.error);
    }

    return pc;
  }, []);

  useEffect(() => {
    let stream = null;

    const init = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: true,
        });
        localStreamRef.current = stream;
        setLocalStream(stream);
        if (localVideoRef.current) {
          localVideoRef.current.srcObject = stream;
        }
      } catch (err) {
        console.error("Failed to get media:", err);
        setError("Could not access camera/microphone. Please check permissions.");
        setConnecting(false);
        return;
      }

      // Connect socket
      const socket = io("/", {
        transports: ["websocket", "polling"],
      });
      socketRef.current = socket;

      socket.on("connect", () => {
        const token = localStorage.getItem("token");
        socket.emit("join-call", { room_id: call.room_id, token });
      });

      socket.on("existing-participants", (data) => {
        setConnecting(false);
        // Create peer connections to existing participants
        const sids = data.sids || [];
        const participants = data.participants || [];
        sids.forEach((sid, i) => {
          if (sid !== socket.id) {
            setPeers((prev) => ({
              ...prev,
              [sid]: { user: participants[i], stream: null },
            }));
            createPeerConnection(sid, true);
          }
        });
      });

      socket.on("user-joined", (data) => {
        setPeers((prev) => ({
          ...prev,
          [data.sid]: { user: data.user, stream: null },
        }));
        // The new user will send an offer to us, so we wait
        createPeerConnection(data.sid, false);
      });

      socket.on("user-left", (data) => {
        const pc = peersRef.current[data.sid];
        if (pc) {
          pc.close();
          delete peersRef.current[data.sid];
        }
        setPeers((prev) => {
          const next = { ...prev };
          delete next[data.sid];
          return next;
        });
      });

      socket.on("offer", async (data) => {
        let pc = peersRef.current[data.from_sid];
        if (!pc) {
          pc = createPeerConnection(data.from_sid, false);
        }
        try {
          await pc.setRemoteDescription(new RTCSessionDescription(data.offer));
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          socket.emit("answer", {
            target_sid: data.from_sid,
            answer: pc.localDescription,
          });
        } catch (err) {
          console.error("Error handling offer:", err);
        }
      });

      socket.on("answer", async (data) => {
        const pc = peersRef.current[data.from_sid];
        if (pc) {
          try {
            await pc.setRemoteDescription(new RTCSessionDescription(data.answer));
          } catch (err) {
            console.error("Error handling answer:", err);
          }
        }
      });

      socket.on("ice-candidate", async (data) => {
        const pc = peersRef.current[data.from_sid];
        if (pc && data.candidate) {
          try {
            await pc.addIceCandidate(new RTCIceCandidate(data.candidate));
          } catch (err) {
            console.error("Error adding ICE candidate:", err);
          }
        }
      });

      socket.on("error", (data) => {
        setError(data.message);
        setConnecting(false);
      });
    };

    init();

    return () => {
      // Cleanup
      if (socketRef.current) {
        socketRef.current.emit("leave-call", { room_id: call.room_id });
        socketRef.current.disconnect();
      }
      Object.values(peersRef.current).forEach((pc) => pc.close());
      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, [call.room_id, createPeerConnection]);

  // Keep local video ref updated
  useEffect(() => {
    if (localVideoRef.current && localStream) {
      localVideoRef.current.srcObject = localStream;
    }
  }, [localStream]);

  const toggleMute = () => {
    if (localStreamRef.current) {
      localStreamRef.current.getAudioTracks().forEach((t) => {
        t.enabled = !t.enabled;
      });
      setIsMuted(!isMuted);
    }
  };

  const toggleVideo = () => {
    if (localStreamRef.current) {
      localStreamRef.current.getVideoTracks().forEach((t) => {
        t.enabled = !t.enabled;
      });
      setIsVideoOff(!isVideoOff);
    }
  };

  const handleEndCall = async () => {
    if (call.created_by === user.id) {
      try {
        await api.endCall(call.id);
      } catch {
        // ignore
      }
    }
    onClose();
  };

  const peerEntries = Object.entries(peers);

  return (
    <div className="call-overlay">
      <div className="call-container">
        <div className="call-header">
          <h2>{call.title}</h2>
          <span className="call-participant-count">
            {peerEntries.length + 1} participant{peerEntries.length !== 0 ? "s" : ""}
          </span>
        </div>

        {error && <p className="call-error">{error}</p>}

        <div className={`call-grid call-grid-${Math.min(peerEntries.length + 1, 4)}`}>
          {/* Local video */}
          <div className="call-video-tile">
            <video
              ref={localVideoRef}
              autoPlay
              playsInline
              muted
              className={`call-video ${isVideoOff ? "video-off" : ""}`}
            />
            {isVideoOff && (
              <div className="call-video-placeholder">
                <div
                  className="call-avatar"
                  style={{ backgroundColor: user?.avatar_color || "#6366f1" }}
                >
                  {(user?.display_name || user?.username || "?")[0].toUpperCase()}
                </div>
              </div>
            )}
            <span className="call-video-label">
              You {isMuted ? "(muted)" : ""}
            </span>
          </div>

          {/* Remote videos */}
          {peerEntries.map(([sid, peer]) => (
            <div key={sid} className="call-video-tile">
              {peer.stream ? (
                <RemoteVideo stream={peer.stream} />
              ) : (
                <div className="call-video-placeholder">
                  <div
                    className="call-avatar"
                    style={{ backgroundColor: peer.user?.avatar_color || "#6366f1" }}
                  >
                    {(peer.user?.display_name || peer.user?.username || "?")[0].toUpperCase()}
                  </div>
                </div>
              )}
              <span className="call-video-label">
                {peer.user?.display_name || peer.user?.username || "Connecting..."}
              </span>
            </div>
          ))}
        </div>

        {connecting && !error && (
          <div className="call-connecting">
            <div className="loading-spinner" />
            <span>Connecting...</span>
          </div>
        )}

        <div className="call-controls">
          <button
            className={`call-control-btn ${isMuted ? "active" : ""}`}
            onClick={toggleMute}
            title={isMuted ? "Unmute" : "Mute"}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              {isMuted ? (
                <>
                  <line x1="1" y1="1" x2="23" y2="23" />
                  <path d="M9 9v3a3 3 0 005.12 2.12M15 9.34V4a3 3 0 00-5.94-.6" />
                  <path d="M17 16.95A7 7 0 015 12v-2m14 0v2c0 .76-.13 1.49-.36 2.18" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </>
              ) : (
                <>
                  <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
                  <path d="M19 10v2a7 7 0 01-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </>
              )}
            </svg>
          </button>

          <button
            className={`call-control-btn ${isVideoOff ? "active" : ""}`}
            onClick={toggleVideo}
            title={isVideoOff ? "Turn on camera" : "Turn off camera"}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              {isVideoOff ? (
                <>
                  <path d="M16.5 9.4l-2-1.4a2 2 0 00-2.3 0l-2 1.4A2 2 0 009 11v2a2 2 0 001.2 1.6l2 1.4a2 2 0 002.3 0l2-1.4A2 2 0 0017 13v-2a2 2 0 00-1.2-1.6z" />
                  <line x1="1" y1="1" x2="23" y2="23" />
                </>
              ) : (
                <>
                  <polygon points="23 7 16 12 23 17 23 7" />
                  <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                </>
              )}
            </svg>
          </button>

          <button
            className="call-control-btn call-end-btn"
            onClick={handleEndCall}
            title="End call"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10.68 13.31a16 16 0 003.41 2.6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7 2 2 0 011.72 2v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91" />
              <line x1="23" y1="1" x2="1" y2="23" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

// Separate component for remote video to handle ref properly
function RemoteVideo({ stream }) {
  const videoRef = useRef(null);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  return (
    <video
      ref={videoRef}
      autoPlay
      playsInline
      className="call-video"
    />
  );
}
