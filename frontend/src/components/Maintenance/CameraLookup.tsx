"use client";

import React, { useState, useRef, useEffect } from "react";
import styles from "./CameraLookup.module.css";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CameraLookupProps {
  onClose: () => void;
  onMatch: (tag: string) => void;
  headers: Record<string, string>;
}

export default function CameraLookup({ onClose, onMatch, headers }: CameraLookupProps) {
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    matched: boolean;
    equipment_tag?: string;
    unit?: string;
    message?: string;
    extracted_text?: string;
  } | null>(null);

  // Camera stream variables
  const [useWebcam, setUseWebcam] = useState(false);
  const [streamActive, setStreamActive] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Attempt to start webcam
  const startWebcam = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setStreamActive(true);
        setUseWebcam(true);
      }
    } catch {
      // Fall back to file upload mode if webcam is blocked or unsupported
      setUseWebcam(false);
      setStreamActive(false);
    }
  };

  // Stop webcam
  const stopWebcam = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach((track) => track.stop());
      videoRef.current.srcObject = null;
    }
    setStreamActive(false);
  };

  useEffect(() => {
    // Try to auto-start webcam
    startWebcam();
    return () => stopWebcam();
  }, []);

  // Capture snapshot from webcam video
  const captureSnapshot = () => {
    if (videoRef.current && canvasRef.current) {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");

      if (ctx) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        canvas.toBlob((blob) => {
          if (blob) {
            const file = new File([blob], "camera_capture.png", { type: "image/png" });
            setImageFile(file);
            setImagePreview(URL.createObjectURL(file));
            stopWebcam();
            setUseWebcam(false);
          }
        }, "image/png");
      }
    }
  };

  // Handle manual file input
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
      setError(null);
      setResult(null);
    }
  };

  // Submit image to backend OCR lookup endpoint
  const handleLookup = async () => {
    if (!imageFile) return;

    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append("file", imageFile);

    try {
      const authHeaders = { ...headers };
      // Let fetch set Content-Type boundary automatically for FormData
      delete (authHeaders as any)["Content-Type"];

      const res = await fetch(`${API_URL}/api/v1/maintenance/equipment/lookup-camera`, {
        method: "POST",
        headers: authHeaders,
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Server returned status ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch {
      setError("Failed to process OCR request. Please check connection and try again.");
    } finally {
      setLoading(false);
    }
  };

  // Confirm match and navigate/scope dashboard
  const handleConfirmMatch = () => {
    if (result && result.matched && result.equipment_tag) {
      onMatch(result.equipment_tag);
      onClose();
    }
  };

  const handleRetake = () => {
    setImageFile(null);
    setImagePreview(null);
    setResult(null);
    startWebcam();
  };

  return (
    <div className={styles.overlay}>
      <div className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="lookup-title">
        <div className={styles.header}>
          <h2 id="lookup-title" className={styles.title}>Camera Equipment Tag Lookup</h2>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close modal">×</button>
        </div>

        <div className={styles.body}>
          {/* Webcam streaming view */}
          {useWebcam && streamActive && (
            <div className={styles.cameraContainer}>
              <video ref={videoRef} className={styles.video} playsInline muted />
              <button className={styles.captureBtn} onClick={captureSnapshot}>
                Capture Tag Plate
              </button>
            </div>
          )}

          {/* Captured or uploaded preview */}
          {imagePreview && (
            <div className={styles.previewContainer}>
              <img src={imagePreview} alt="Tag plate preview" className={styles.previewImage} />
              <div className={styles.previewActions}>
                <button className={styles.retakeBtn} onClick={handleRetake}>
                  Capture / Upload another
                </button>
                <button
                  className={styles.lookupBtn}
                  onClick={handleLookup}
                  disabled={loading}
                >
                  {loading ? "Analyzing OCR..." : "Lookup Tag"}
                </button>
              </div>
            </div>
          )}

          {/* File Picker fallback */}
          {!streamActive && !imagePreview && (
            <div className={styles.fallbackPicker}>
              <div className={styles.pickerIcon}>📷</div>
              <p className={styles.pickerPrompt}>
                Allow camera permissions or upload a photograph of the physical equipment tag plate.
              </p>
              <label className={styles.fileInputLabel}>
                Upload Photo
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className={styles.fileInput}
                  onChange={handleFileChange}
                />
              </label>
            </div>
          )}

          {/* Errors banner */}
          {error && <div className={styles.bannerError} role="alert">{error}</div>}

          {/* OCR Lookup Results banner */}
          {result && (
            <div className={styles.resultContainer}>
              {result.matched ? (
                <div className={styles.successBox}>
                  <div className={styles.successHeader}>✓ Match Found</div>
                  <div className={styles.tagLabel}>{result.equipment_tag}</div>
                  {result.unit && (
                    <div className={styles.unitLabel}>Unit: {result.unit}</div>
                  )}
                  {result.message && <p className={styles.resultMsg}>{result.message}</p>}
                  <button className={styles.confirmBtn} onClick={handleConfirmMatch}>
                    Go to Asset Timeline
                  </button>
                </div>
              ) : (
                <div className={styles.failureBox}>
                  <div className={styles.failureHeader}>✗ No Direct Match</div>
                  <p className={styles.resultMsg}>
                    {result.message || "Could not resolve matches. Extracted text:"}
                  </p>
                  <pre className={styles.extractedText}>{result.extracted_text}</pre>
                </div>
              )}
            </div>
          )}
        </div>

        <canvas ref={canvasRef} style={{ display: "none" }} />
      </div>
    </div>
  );
}
