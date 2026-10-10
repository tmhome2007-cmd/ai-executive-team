/** Local CSS 3D room; movement is presentation, state comes only from loaded records. */
"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import CharacterAvatar from "./character-avatar";
import type { ExecutiveProfile } from "./company-records";

export default function OfficeFloor3D({
  profile,
  available,
  stale,
  actions,
  onInspect,
}: {
  profile?: ExecutiveProfile;
  available: boolean;
  stale: boolean;
  actions: {
    id: number;
    proposed_by: string;
    status: string;
    action_description: string;
  }[];
  onInspect: () => void;
}) {
  const container = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(false);
  const [pageVisible, setPageVisible] = useState(false);
  const [motion, setMotion] = useState(false);
  const [reduced, setReduced] = useState(true);
  const [angle, setAngle] = useState(-28);
  const [zoom, setZoom] = useState(85);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updateMotion = () => setReduced(media.matches);
    const updateVisibility = () => setPageVisible(!document.hidden);
    updateMotion();
    updateVisibility();
    media.addEventListener("change", updateMotion);
    document.addEventListener("visibilitychange", updateVisibility);
    const observer = new IntersectionObserver(([entry]) =>
      setVisible(entry.isIntersecting),
    );
    if (container.current) observer.observe(container.current);
    return () => {
      observer.disconnect();
      media.removeEventListener("change", updateMotion);
      document.removeEventListener("visibilitychange", updateVisibility);
    };
  }, []);
  const records = actions.filter((a) => a.proposed_by.toLowerCase() === "ceo");
  const active = records.find((a) => a.status === "executing");
  const known = available && !stale;
  const state = !known
    ? "Unknown — records unavailable or stale"
    : active
      ? `Recorded execution · Action #${active.id}`
      : "Idle presentation — no executing action in loaded records";
  const playing = motion && visible && pageVisible && !reduced;
  return (
    <section
      ref={container}
      className="command-card office-3d"
      aria-label="3D executive floor"
    >
      <div className="office-3d-heading">
        <div>
          <p className="text-xs text-teal-300">FLOOR 03 · LOCAL PROTOTYPE</p>
          <h3 className="text-xl font-semibold">Kai’s executive office</h3>
        </div>
        <button className="office-filter" onClick={onInspect}>
          Inspect CEO records
        </button>
      </div>
      <p className="text-sm text-gray-400 mt-2">
        A perspective room with the saved character portrait. Decorative movement is
        fictional; this is not live presence or proof of work.
      </p>
      <div className="office-3d-controls">
        <label>
          Camera angle
          <input
            aria-label="Office camera angle"
            type="range"
            min="-55"
            max="20"
            value={angle}
            onChange={(e) => setAngle(Number(e.target.value))}
          />
        </label>
        <label>
          Room zoom
          <input
            aria-label="Office room zoom"
            type="range"
            min="60"
            max="100"
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
          />
        </label>
        <button
          className="office-filter"
          onClick={() => {
            setAngle(-28);
            setZoom(85);
          }}
        >
          Reset camera
        </button>
        <button
          className="office-filter"
          aria-pressed={motion}
          disabled={reduced}
          onClick={() => setMotion(!motion)}
        >
          {motion ? "Pause decorative movement" : "Enable decorative movement"}
        </button>
      </div>
      <p className="text-xs text-gray-400">
        {reduced
          ? "Reduced motion: animation disabled."
          : playing
            ? "Decorative movement enabled."
            : "Decorative movement paused."}{" "}
        Automatically pauses offscreen and when this tab is hidden.
      </p>
      <div className="office-3d-viewport" aria-label="Executive room illustration">
        <div
          className="office-3d-room"
          style={
            {
              "--room-zoom": zoom / 100,
              "--room-angle": `${angle}deg`,
            } as CSSProperties
          }
          aria-hidden="true"
        >
          <div className="office-3d-ground" />
          <div className="office-3d-back">
            <span>EXECUTIVE TEAM</span>
            <div className="office-3d-window" />
          </div>
          <div className="office-3d-side" />
          <div className="office-3d-rug" />
          <div className="office-3d-desk">
            <span />
          </div>
          <div className="office-3d-seat" />
          <div className="office-3d-plant">✦</div>
          <div
            className="office-3d-person"
            style={{ animationPlayState: playing ? "running" : "paused" }}
          >
            <CharacterAvatar
              name={profile?.name || "Kai Akira"}
              presentation={profile?.presentation}
            />
          </div>
        </div>
      </div>
      <div className="office-3d-state">
        <strong>{profile?.name || "CEO profile unavailable"}</strong>
        <p>{state}</p>
        {known && active && (
          <p className="text-sm text-gray-400">{active.action_description}</p>
        )}
      </div>
      <details className="mt-3">
        <summary>Accessible room description &amp; recorded state</summary>
        <p className="text-sm mt-2">
          Executive floor: a desk, chair, window, rug and plant.{" "}
          {profile?.presentation?.appearance.description ||
            "Character appearance is unavailable."}{" "}
          {state}. The existing 2D office and inspector remain below; use them to review
          the underlying records.
        </p>
      </details>
    </section>
  );
}
