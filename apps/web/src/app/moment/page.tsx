"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  GOAL_LABELS,
  OCCASION_LABELS,
  TIME_LABELS,
} from "@mirror-ops/config";
import {
  GOALS,
  OCCASIONS,
  TIME_OPTIONS,
  type Goal,
  type Occasion,
  type TimeAvailable,
} from "@mirror-ops/types";

import { Action } from "@/components/Action";
import { ChoiceGroup } from "@/components/ChoiceGroup";
import { Notice } from "@/components/Notice";
import { Stage } from "@/components/Stage";
import { ApiError, createMoment } from "@/lib/api";
import { readSessionId } from "@/lib/session";

const OCCASION_OPTIONS = OCCASIONS.map((value) => ({
  value,
  label: OCCASION_LABELS[value] ?? value,
}));
const GOAL_OPTIONS = GOALS.map((value) => ({ value, label: GOAL_LABELS[value] ?? value }));
const TIME_OPTIONS_UI = TIME_OPTIONS.map((value) => ({
  value,
  label: TIME_LABELS[value] ?? value,
}));

/**
 * Écran 02 — THE MOMENT.
 *
 * Trois questions, pas dix (Doc 03 §6). Occasion + objectif + temps suffisent
 * au moteur ; tout le reste se déduit.
 */
export default function MomentPage() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [occasion, setOccasion] = useState<Occasion | null>(null);
  const [goal, setGoal] = useState<Goal | null>(null);
  const [time, setTime] = useState<TimeAvailable | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = readSessionId();
    if (!id) router.replace("/");
    else setSessionId(id);
  }, [router]);

  const ready = Boolean(sessionId && occasion && goal && time);

  async function submit() {
    if (!sessionId || !occasion || !goal || !time) return;
    setSaving(true);
    setError(null);
    try {
      await createMoment({ sessionId, occasion, goal, timeAvailable: time });
      router.push("/look");
    } catch (cause) {
      if (cause instanceof ApiError && cause.code === "SESSION_EXPIRED") {
        router.replace("/");
        return;
      }
      setError(cause instanceof ApiError ? cause.message : "Something went wrong.");
      setSaving(false);
    }
  }

  return (
    <Stage step="/moment" back="/">
      <div className="enter enter--1">
        <p className="eyebrow">Step one</p>
        <h1 className="heading">What&apos;s the moment?</h1>
        <p className="body" style={{ marginBottom: 28 }}>
          The same outfit can be right for a dinner and wrong for a wedding. Mirror Ops
          judges your look against the moment, not in the abstract.
        </p>
      </div>

      <div className="enter enter--2">
        <ChoiceGroup
          legend="The occasion"
          options={OCCASION_OPTIONS}
          value={occasion}
          onChange={setOccasion}
        />
        <ChoiceGroup
          legend="How you want to come across"
          options={GOAL_OPTIONS}
          value={goal}
          onChange={setGoal}
        />
        <ChoiceGroup
          legend="Time you have"
          options={TIME_OPTIONS_UI}
          value={time}
          onChange={setTime}
        />
      </div>

      <div className="spacer" />

      <div className="stage__foot enter enter--3">
        {error ? <Notice title={error} /> : null}
        <Action onClick={submit} disabled={!ready || saving}>
          {saving ? "Saving…" : "Continue"}
        </Action>
        <p className="fine">
          Short on time changes the answer: Mirror Ops won&apos;t suggest something you
          can&apos;t actually do before you leave.
        </p>
      </div>
    </Stage>
  );
}
