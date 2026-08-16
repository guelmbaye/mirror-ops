"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Action } from "@/components/Action";
import { CameraCapture, cameraIsAvailable } from "@/components/CameraCapture";
import { Notice } from "@/components/Notice";
import { Stage } from "@/components/Stage";
import { DRESS_LEVELS, ELEMENT_LABELS, oneNotchDown } from "@mirror-ops/config";
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
  // AUCUNE valeur par defaut.
  //
  // Pre-cocher haut/bas/chaussures et laisser veste/accessoires decoches
  // apprenait a l'utilisateur que les defauts sont corrects — il n'inspectait
  // donc pas les cases vides, et une absence qu'il n'avait jamais affirmee
  // partait au moteur. Resultat : « Add a jacket » a quelqu'un qui en porte une.
  //
  // Chaque piece exige desormais un geste. Une case vide signifie « j'ai
  // parcouru la liste et je ne porte pas ca », ce qui est une affirmation
  // reelle.
  const [worn, setWorn] = useState<Set<OutfitElement>>(() => new Set<OutfitElement>());
  // Sans cette reponse, tout look est lu comme « moyennement habille » : un
  // entretien et un voyage rendent alors le meme verdict a deux points pres, et
  // la these du produit devient invisible. Elle a d'abord ete facultative — la
  // demonstration echouait silencieusement. Elle est desormais requise.
  const [dress, setDress] = useState<number | null>(null);
  // La piece qui detonne, si l'utilisateur en signale une.
  //
  // Sans elle, chaque piece porte le meme niveau d'habillement et aucune ne se
  // detache : le verdict ne peut alors JAMAIS nommer de coupable, et se limite
  // a « as a whole, this look sits below… ». La phrase la plus utile du
  // produit — « the shoes reduce the level of formality » — etait donc
  // inatteignable depuis l'interface.
  //
  // Le moteur ne se contente pas de repeter cette declaration : il decide si
  // cet ecart compte POUR CE MOMENT. Des baskets ne penalisent pas un voyage.
  const [oddOne, setOddOne] = useState<OutfitElement | null>(null);
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
    // Une piece qu'on ne porte plus ne peut pas etre celle qui detonne.
    setOddOne((current) => (current === element ? null : current));
  }

  function goToAnalysis() {
    // On declare aussi ce qui est ABSENT : c'est cette information qui empeche
    // MIRROR OPS de recommander de changer une piece qui n'est pas la.
    const outfit: OutfitIn = {};
    for (const element of OUTFIT_ELEMENTS) {
      if (!worn.has(element) || dress === null) {
        outfit[element] = { present: worn.has(element) };
        continue;
      }
      // La pièce signalée descend d'UN cran dans l'échelle affichée — pas
      // jusqu'au plancher. C'est l'écart qui permet au verdict de la nommer,
      // sans sur-interpréter ce que l'utilisateur a dit.
      const level = element === oddOne ? oneNotchDown(dress) : dress;
      outfit[element] = { present: true, formality: level, structure: level };
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
            <legend className="wearing__legend">
              Tap everything you&apos;re wearing
            </legend>
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
                  <p className="wearing__warning" style={{ marginTop: 8 }}>
                    Pick one. It&apos;s what lets Mirror Ops judge the same look
                    differently for an interview and for a flight.
                  </p>
                ) : (
                  <div style={{ marginTop: 16 }}>
                    <p className="wearing__legend" style={{ margin: "0 0 4px" }}>
                      Anything more casual than the rest?{" "}
                      <span style={{ textTransform: "none", letterSpacing: 0 }}>
                        (optional)
                      </span>
                    </p>
                    <p className="fine" style={{ margin: "0 0 10px" }}>
                      Same pieces, different question: which one sits below the rest.
                    </p>
                    {/* Rendu volontairement distinct de la premiere liste :
                        les memes mots, la meme grille et le meme style faisaient
                        lire les deux questions comme un doublon. */}
                    <div className="wearing__chips">
                      {[...worn].map((element) => (
                        <button
                          key={element}
                          type="button"
                          className="chip chip--sub"
                          aria-pressed={oddOne === element}
                          onClick={() => setOddOne(oddOne === element ? null : element)}
                        >
                          {oddOne === element ? "↓ " : ""}
                          {ELEMENT_LABELS[element] ?? element}
                        </button>
                      ))}
                    </div>
                    <p className="fine" style={{ marginTop: 8 }}>
                      {oddOne
                        ? `Mirror Ops will weigh whether the ${(ELEMENT_LABELS[oddOne] ?? oddOne).toLowerCase()} actually matters for this moment — it may not.`
                        : "Sneakers with a suit, say. Skip it if everything is on the same level."}
                    </p>
                  </div>
                )}
              </div>
            ) : null}

            {worn.size === 0 ? (
              // Sans aucune piece declaree, le moteur n'a rien a juger et
              // refuserait plus loin. Autant le dire ici, pas trois ecrans plus tard.
              <p className="wearing__summary wearing__summary--empty">
                Tap each piece you have on. Mirror Ops can&apos;t judge a look it knows
                nothing about — and it won&apos;t guess.
              </p>
            ) : (
              <>
                <p className="wearing__summary">
                  Mirror Ops will read this as: <strong>{listOf([...worn])}</strong>
                  {missing.length > 0 ? (
                    <>
                      , and{" "}
                      <strong className="wearing__missing">no {listOf(missing)}</strong>.
                    </>
                  ) : (
                    "."
                  )}
                </p>

                {/* L'absence est l'affirmation risquee : c'est elle qui produit
                    « Add a jacket ». On la rend impossible a manquer. */}
                {missing.length > 0 ? (
                  <p className="wearing__warning">
                    If you <em>are</em> wearing {listOf(missing)}, tap{" "}
                    {missing.length > 1 ? "them" : "it"} above — otherwise Mirror Ops
                    may tell you to add {missing.length > 1 ? "one of them" : "one"}.
                  </p>
                ) : null}
              </>
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
            <Action onClick={goToAnalysis} disabled={worn.size === 0 || dress === null}>
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
