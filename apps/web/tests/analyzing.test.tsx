/**
 * Régression : l'écran d'analyse doit avancer jusqu'au bout, y compris quand
 * React monte le composant deux fois (StrictMode en développement).
 *
 * Le bug corrigé ici : le garde-fou anti-double-appel et le drapeau
 * d'annulation se neutralisaient. L'API répondait 201, puis le parcours
 * s'arrêtait en silence sur « Reading your look ».
 */

import { act, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

const replace = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push }),
}));

const analyzeAppearance = vi.fn();
const evaluateOneChange = vi.fn();
const getSessionDetail = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    analyzeAppearance: (...args: unknown[]) => analyzeAppearance(...args),
    evaluateOneChange: (...args: unknown[]) => evaluateOneChange(...args),
    getSessionDetail: (...args: unknown[]) => getSessionDetail(...args),
  };
});

vi.mock("@/lib/session", () => ({
  readSessionId: () => "session-under-test",
  stepKey: (id: string, step: string) => `${id}:${step}`,
  // L'empreinte des entrées : sans elle, une correction reste sans effet.
  fingerprint: (...parts: unknown[]) => parts.join("|"),
}));

vi.mock("@/lib/photo", () => ({
  getPhoto: () => ({
    file: new File(["x"], "look.jpg", { type: "image/jpeg" }),
    previewUrl: "blob:look",
  }),
  getOutfit: () => ({ jacket: { present: false }, top: { present: true } }),
  getMoment: () => "interview|professional|<5m",
}));

import { ApiError } from "@/lib/api";
import AnalyzingPage from "@/app/analyzing/page";

/** Une réponse qui met un tour de boucle à revenir, comme un vrai appel réseau. */
function deferred<T>(value: T) {
  return new Promise<T>((resolve) => setTimeout(() => resolve(value), 10));
}

describe("écran d'analyse", () => {
  beforeEach(() => {
    replace.mockReset();
    push.mockReset();
    analyzeAppearance.mockReset().mockImplementation(() => deferred({ analysis_id: "a1" }));
    evaluateOneChange.mockReset().mockImplementation(() => deferred({ recommendation: {} }));
    getSessionDetail
      .mockReset()
      .mockImplementation(() => deferred({ analysis: null, recommendation: null }));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("va jusqu'à la décision malgré le double montage de StrictMode", async () => {
    render(
      <StrictMode>
        <AnalyzingPage />
      </StrictMode>,
    );

    // L'orchestration démarre.
    expect(await screen.findByText("Reading your look")).toBeDefined();

    // Et surtout : elle ne s'y arrête pas.
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/one-change"), {
      timeout: 3000,
    });
  });

  test("ne consomme qu'une analyse et une décision par parcours", async () => {
    render(
      <StrictMode>
        <AnalyzingPage />
      </StrictMode>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/one-change"), {
      timeout: 3000,
    });

    expect(analyzeAppearance).toHaveBeenCalledTimes(1);
    expect(evaluateOneChange).toHaveBeenCalledTimes(1);
  });

  test("affiche un état d'échec exploitable quand l'analyse échoue", async () => {
    const { ApiError } = await import("@/lib/api");
    analyzeAppearance.mockRejectedValueOnce(
      new ApiError("INVALID_IMAGE", "We need a clearer view of your look.", true, 422),
    );

    render(
      <StrictMode>
        <AnalyzingPage />
      </StrictMode>,
    );

    expect(
      await screen.findByText("We need a clearer view of your look."),
    ).toBeDefined();
    expect(replace).not.toHaveBeenCalledWith("/one-change");
  });

  test("se rattrape sur l'état serveur si l'orchestration se bloque", async () => {
    // Le pire cas : la promesse d'analyse ne revient jamais côté navigateur,
    // alors que l'API a bel et bien répondu 201 et enregistré la décision.
    vi.useFakeTimers();
    analyzeAppearance.mockImplementation(() => new Promise(() => {}));
    getSessionDetail.mockResolvedValue({
      analysis: { analysis_id: "a1" },
      recommendation: { id: "r1" },
    });

    render(
      <StrictMode>
        <AnalyzingPage />
      </StrictMode>,
    );

    // Le filet de sécurité relit la session toutes les 8 s.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(9000);
    });

    expect(getSessionDetail).toHaveBeenCalled();
    expect(replace).toHaveBeenCalledWith("/one-change");
  });
  test("transmet la tenue déclarée à l'analyse", async () => {
    render(
      <StrictMode>
        <AnalyzingPage />
      </StrictMode>,
    );

    await waitFor(() => expect(analyzeAppearance).toHaveBeenCalled());
    const call = analyzeAppearance.mock.calls[0][0] as { outfit?: Record<string, unknown> };

    // Sans cela, MIRROR OPS supposerait une veste et pourrait recommander de la
    // changer alors qu'il n'y en a pas.
    expect(call.outfit).toEqual({ jacket: { present: false }, top: { present: true } });
  });
  test("la clé d'idempotence suit les entrées, pas seulement l'étape", async () => {
    render(
      <StrictMode>
        <AnalyzingPage />
      </StrictMode>,
    );

    await waitFor(() => expect(analyzeAppearance).toHaveBeenCalled());
    const call = analyzeAppearance.mock.calls[0][0] as { idempotencyKey: string };

    // La tenue déclarée doit apparaître dans la clé : deux tenues différentes
    // sur la même photo doivent produire deux analyses.
    expect(call.idempotencyKey).toContain("analyze:");
    expect(call.idempotencyKey).toContain("jacket");
    // Le moment aussi : l'analyse evalue l'adequation AU moment, donc changer
    // d'occasion doit produire une nouvelle cle.
    expect(call.idempotencyKey).toContain("interview");
  });
  test("le filet de sécurité s'arrête quand l'analyse a échoué", async () => {
    vi.useFakeTimers();
    analyzeAppearance.mockRejectedValue(
      new ApiError("INVALID_IMAGE", "This image is only 143 pixels wide.", true, 422),
    );

    try {
      render(
        <StrictMode>
          <AnalyzingPage />
        </StrictMode>,
      );
      await vi.waitFor(() => expect(analyzeAppearance).toHaveBeenCalled());
      getSessionDetail.mockClear();

      // Le watchdog interrogeait le serveur toutes les huit secondes,
      // indéfiniment — deux minutes observées en production — pendant que
      // l'utilisateur regardait un écran figé. Un échec franc n'est pas un
      // blocage : il n'y a rien à récupérer.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });

      expect(getSessionDetail).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});
