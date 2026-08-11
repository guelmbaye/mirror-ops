"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * La preuve visuelle.
 *
 * Le curseur est le héros de l'écran : on tire, une seule chose a bougé.
 * Utilisable à la souris, au doigt et au clavier — les flèches déplacent la
 * séparation, ce qui rend la comparaison accessible sans pointeur.
 */
export function BeforeAfter({
  beforeUrl,
  afterUrl,
  alt = "Your look before and after the change",
}: {
  beforeUrl: string;
  afterUrl: string;
  alt?: string;
}) {
  const frame = useRef<HTMLDivElement | null>(null);
  const dragging = useRef(false);
  const [split, setSplit] = useState(50);

  const moveTo = useCallback((clientX: number) => {
    const box = frame.current?.getBoundingClientRect();
    if (!box || box.width === 0) return;
    const ratio = ((clientX - box.left) / box.width) * 100;
    setSplit(Math.max(0, Math.min(100, ratio)));
  }, []);

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      if (!dragging.current) return;
      event.preventDefault();
      moveTo(event.clientX);
    };
    const stop = () => {
      dragging.current = false;
    };
    window.addEventListener("pointermove", onMove, { passive: false });
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
  }, [moveTo]);

  const onKeyDown = (event: React.KeyboardEvent) => {
    const step = event.shiftKey ? 10 : 4;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      setSplit((value) => Math.max(0, value - step));
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      setSplit((value) => Math.min(100, value + step));
    } else if (event.key === "Home") {
      setSplit(0);
    } else if (event.key === "End") {
      setSplit(100);
    }
  };

  return (
    <div
      ref={frame}
      className="compare"
      role="slider"
      tabIndex={0}
      aria-label="Drag to compare before and after"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(split)}
      aria-valuetext={`${Math.round(split)}% of the new look shown`}
      onKeyDown={onKeyDown}
      onPointerDown={(event) => {
        dragging.current = true;
        moveTo(event.clientX);
      }}
    >
      <div className="compare__layer">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={beforeUrl} alt={alt} draggable={false} />
      </div>
      <div className="compare__layer" style={{ clipPath: `inset(0 0 0 ${split}%)` }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={afterUrl} alt="" draggable={false} />
      </div>

      <span className="compare__tag compare__tag--before">Before</span>
      <span className="compare__tag compare__tag--after">After</span>

      <div className="compare__handle" style={{ left: `${split}%` }}>
        <span className="compare__grip" aria-hidden="true">
          ←→
        </span>
      </div>
    </div>
  );
}
