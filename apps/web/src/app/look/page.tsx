"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Action } from "@/components/Action";
import { CameraCapture, cameraIsAvailable } from "@/components/CameraCapture";
import { Notice } from "@/components/Notice";
import { Stage } from "@/components/Stage";
import { DRESS_LEVELS, ELEMENT_LABELS } from "@mirror-ops/config";
import { OUTFIT_ELEMENTS, type OutfitElement, type OutfitIn } from "@mirror-ops/types";

import { clearPhoto, getOutfit, getPhoto, setOutfit, setPhoto } from "@/lib/photo";
import { readSessionId } from "@/lib/session";

const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];

/**
 * Écran 03 — YOUR LOOK.
 *
 * On parle à quelqu'un qui se prépare, pas à un pipeline de vision par
 * ordinateur (Doc 03 §8). Sur mobile, `capture="environment"` ouvre directement
 * l'appareil photo ; l'import de fichier reste le repli sur desktop.
 */
export default function LookPage() {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [shooting, setShooting] = useState(false);
  // Ce que la personne porte. Par defaut : haut, bas, chaussures — la tenue la
  // plus courante. Veste et accessoires se declarent, ils ne se supposent pas.
  const [worn, setWorn] = useState<Set<OutfitElement>>(
    () => new Set<OutfitElement>(["top", "bottom", "shoes"]),
  );
  // Sans cette réponse, le moteur applique le même a priori à tout le monde et
  // rend le même verdict pour un mariage et pour un voyage.
  const [dress, setDress] = useState<number | null>(null);
  // Décidé après le montage : `window` n'existe pas au rendu serveur.
  const [hasCamera, setHasCamera] = useState(false);

  useEffect(() => {
    if (!readSessionId()) {
      router.replace("/");
      return;
    }
    setPreview(getPhoto()?.previewUrl ?? null);
    setHasCamera(cameraIsAvailable());
    const saved = getOutfit();
    if (saved) {
      setWorn(
        new Set(
          OUTFIT_ELEMENTS.filter((element) => saved[element]?.present) as OutfitElement[],
        ),
      );
    }
  }, [router]);

  function accept(file: File | undefined) {
    if (!file) return;

    // Le backend revalide tout : ces contrôles servent uniquement à éviter un
    // aller-retour inutile et à répondre immédiatement.
    if (!ACCEPTED.includes(file.type)) {
      setProblem("That file isn't a photo Mirror Ops can read. Use a JPEG, PNG or WebP.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setProblem("That photo is over 10 MB. Take a new one or pick a smaller file.");
      return;
    }

    setProblem(null);
    setPreview(setPhoto(file));
  }

  function retake() {
    clearPhoto();
    setPreview(null);
    setProblem(null);
    if (hasCamera) setShooting(true);
    else fileInput.current?.click();
  }

  const missing = OUTFIT_ELEMENTS.filter((element) => !worn.has(element));

  /** « jacket, top and shoes » — une énumération lisible, pas une liste technique. */
  function listOf(elements: readonly string[]): string {
    const labels = elements.map((e) => (ELEMENT_LABELS[e] ?? e).toLowerCase());
    if (labels.length <= 1) return labels[0] ?? "";
    return `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`;
  }

  function toggle(element: OutfitElement) {
    setWorn((current) => {
      const next = new Set(current);
      if (next.has(element)) next.delete(element);
      else next.add(element);
      return next;
    });
  }

  function goToAnalysis() {
    // On declare aussi ce qui est ABSENT : c'est cette information qui empeche
    // MIRROR OPS de recommander de changer une piece qui n'est pas la.
    const outfit: OutfitIn = {};
    for (const element of OUTFIT_ELEMENTS) {
      outfit[element] =
        worn.has(element) && dress !== null
          ? { present: true, formality: dress, structure: dress }
          : { present: worn.has(element) };
    }
    setOutfit(outfit);
    router.push("/analyzing");
  }

  return (
    <Stage step="/look" back="/moment">
      <div className="enter enter--1">
        <p className="eyebrow">Step two</p>
        <h1 className="heading">Show us where you&apos;re starting.</h1>
        <p className="body" style={{ marginBottom: 20 }}>
          Stand in good light and show as much of your look as you can.
        </p>
      </div>

      {problem ? <Notice title={problem} /> : null}

      <div className="enter enter--2">
        {shooting ? (
          <CameraCapture
            onCapture={(file) => {
              setShooting(false);
              accept(file);
            }}
            onCancel={() => setShooting(false)}
          />
        ) : (
          <>
        <div className={preview ? "capture capture--filled" : "capture"}>
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className="capture__img" src={preview} alt="Your current look" />
          ) : (
            <>
              <p className="eyebrow" style={{ margin: 0 }}>
                Your look
              </p>
              <p className="body capture__hint">
                A full-length photo works best. Head to knee is fine too.
              </p>
            </>
          )}
        </div>

        <input
          ref={fileInput}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          className="sr-only"
          onChange={(event) => accept(event.target.files?.[0])}
        />

        {preview ? (
          <fieldset className="wearing">
            <legend className="wearing__legend">What are you wearing?</legend>
            <div className="wearing__chips">
              {OUTFIT_ELEMENTS.map((element) => (
                <button
                  key={element}
                  type="button"
                  className="chip"
                  aria-pressed={worn.has(element)}
                  onClick={() => toggle(element)}
                >
                  {ELEMENT_LABELS[element] ?? element}
                </button>
              ))}
            </div>
            {/* La selection est une AFFIRMATION envoyee au moteur. Tant qu'elle
                reste implicite, une case oubliee produit « Add a jacket » a
                quelqu'un qui en porte une. On l'ecrit donc en toutes lettres. */}
            {worn.size > 0 ? (
              <div className="dress">
                <p className="wearing__legend" style={{ margin: "18px 0 10px" }}>
                  How dressed up is it?
                </p>
                <div className="wearing__chips">
                  {DRESS_LEVELS.map((level) => (
                    <button
                      key={level.label}
                      type="button"
                      className="chip"
                      aria-pressed={dress === level.value}
                      onClick={() => setDress(level.value)}
                    >
                      {level.label}
                    </button>
                  ))}
                </div>
                {dress === null ? (
                  <p className="fine" style={{ marginTop: 8 }}>
                    Skip it if you like — Mirror Ops will decide anyway, with less certainty.
                  </p>
                ) : null}
              </div>
            ) : null}

            {worn.size === 0 ? (
              // Sans aucune piece declaree, le moteur n'a rien a juger et
              // refuserait plus loin. Autant le dire ici, pas trois ecrans plus tard.
              <p className="wearing__summary wearing__summary--empty">
                Pick at least one piece — Mirror Ops can&apos;t judge a look it knows nothing
                about.
              </p>
            ) : (
            <p className="wearing__summary">
              Mirror Ops will read this as:{" "}
              <strong>{worn.size > 0 ? listOf([...worn]) : "nothing declared"}</strong>
              {missing.length > 0 ? (
                <>
                  {" "}— and <strong className="wearing__missing">no {listOf(missing)}</strong>.
                </>
              ) : (
                "."
              )}
            </p>
            )}
            <p className="fine" style={{ marginTop: 8 }}>
              Mirror Ops won&apos;t suggest changing something you aren&apos;t wearing — and it
              won&apos;t pretend to have seen it.
            </p>
          </fieldset>
        ) : null}

        {preview ? (
          <div className="capture__row">
            <Action variant="ghost" onClick={retake}>
              Retake
            </Action>
            <Action onClick={goToAnalysis} disabled={worn.size === 0}>
              Continue
            </Action>
          </div>
        ) : hasCamera ? (
          <div className="capture__row">
            <Action variant="ghost" onClick={() => fileInput.current?.click()}>
              Upload a photo
            </Action>
            <Action onClick={() => setShooting(true)}>Take photo</Action>
          </div>
        ) : (
          // Sans caméra utilisable, un seul bouton : deux libellés pour la même
          // action donneraient l'illusion d'un choix qui n'existe pas.
          <div style={{ marginTop: 12 }}>
            <Action onClick={() => fileInput.current?.click()}>Choose a photo</Action>
          </div>
        )}
          </>
        )}
      </div>

      <div className="spacer" />

      <div className="stage__foot enter enter--3">
        <p className="fine">
          Your photo is sent to Mirror Ops for this session only, then deleted. It never
          leaves the flow with your name attached — there isn&apos;t one.
        </p>
      </div>
    </Stage>
  );
}
