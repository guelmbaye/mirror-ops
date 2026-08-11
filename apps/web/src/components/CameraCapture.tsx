"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Action } from "@/components/Action";
import { Notice } from "@/components/Notice";

/**
 * Prise de photo dans le navigateur.
 *
 * Sur mobile, l'attribut `capture` d'un `<input file>` suffit à ouvrir
 * l'appareil photo. Sur ordinateur il est purement ignoré : un bouton
 * « Take photo » y ouvrait donc le même sélecteur de fichiers que
 * « Upload photo » — deux libellés différents pour un comportement identique,
 * ce qui est un mensonge d'interface.
 *
 * Ce composant ouvre un vrai flux vidéo quand le navigateur le permet, et le
 * dit franchement quand il ne le permet pas.
 */
export function CameraCapture({
  onCapture,
  onCancel,
}: {
  onCapture: (file: File) => void;
  onCancel: () => void;
}) {
  const video = useRef<HTMLVideoElement | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const [ready, setReady] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const stop = useCallback(() => {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function open() {
      try {
        const media = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment", width: { ideal: 1080 }, height: { ideal: 1440 } },
          audio: false,
        });
        if (cancelled) {
          media.getTracks().forEach((track) => track.stop());
          return;
        }
        stream.current = media;
        if (video.current) {
          video.current.srcObject = media;
          await video.current.play().catch(() => undefined);
        }
        setReady(true);
      } catch (cause) {
        if (cancelled) return;
        const name = cause instanceof DOMException ? cause.name : "";
        setProblem(
          name === "NotAllowedError"
            ? "Camera access was blocked. Allow it in your browser, or upload a photo instead."
            : name === "NotFoundError"
              ? "No camera found on this device. Upload a photo instead."
              : "We couldn't open the camera here. Upload a photo instead.",
        );
      }
    }

    void open();
    return () => {
      cancelled = true;
      stop();
    };
  }, [stop]);

  function shoot() {
    const element = video.current;
    if (!element || !element.videoWidth) return;

    const canvas = document.createElement("canvas");
    canvas.width = element.videoWidth;
    canvas.height = element.videoHeight;
    canvas.getContext("2d")?.drawImage(element, 0, 0);

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        stop();
        onCapture(new File([blob], "look.jpg", { type: "image/jpeg" }));
      },
      "image/jpeg",
      0.92,
    );
  }

  if (problem) {
    return (
      <Notice
        title={problem}
        actions={
          <Action variant="ghost" onClick={onCancel}>
            Back
          </Action>
        }
      />
    );
  }

  return (
    <>
      <div className="capture capture--filled capture--live">
        <video ref={video} className="capture__video" playsInline muted autoPlay />
        {!ready ? <p className="fine capture__hint">Opening the camera…</p> : null}
      </div>
      <div className="capture__row">
        <Action
          variant="ghost"
          onClick={() => {
            stop();
            onCancel();
          }}
        >
          Cancel
        </Action>
        <Action onClick={shoot} disabled={!ready}>
          Take the photo
        </Action>
      </div>
    </>
  );
}

/** Le navigateur peut-il ouvrir un flux vidéo ? Évite de proposer l'impossible. */
export function cameraIsAvailable(): boolean {
  return (
    typeof navigator !== "undefined" &&
    typeof navigator.mediaDevices?.getUserMedia === "function" &&
    // getUserMedia exige un contexte sécurisé : https, ou localhost.
    (typeof window === "undefined" || window.isSecureContext)
  );
}
