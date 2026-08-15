/**
 * La photo capturée vit en mémoire, le temps d'un parcours.
 *
 * Elle n'est écrite ni dans le stockage local, ni dans un cookie : le seul
 * endroit où elle est conservée est le stockage temporaire du backend, effacé à
 * expiration. Si l'onglet est rechargé avant l'analyse, l'écran de capture le
 * dit et redemande la photo plutôt que de faire semblant.
 */

import type { OutfitIn } from "@mirror-ops/types";

let current: { file: File; previewUrl: string } | null = null;
let declaredOutfit: OutfitIn | null = null;
let declaredMoment: string | null = null;

export function setPhoto(file: File): string {
  clearPhoto();
  const previewUrl = URL.createObjectURL(file);
  current = { file, previewUrl };
  return previewUrl;
}

export function getPhoto(): { file: File; previewUrl: string } | null {
  return current;
}

export function clearPhoto(): void {
  if (current) URL.revokeObjectURL(current.previewUrl);
  current = null;
  declaredOutfit = null;
  declaredMoment = null;
}

/**
 * Ce que la personne declare porter.
 *
 * Sans cette information, MIRROR OPS suppose que toutes les pieces sont
 * presentes — et peut recommander de changer une veste qui n'existe pas. Le
 * produit affirmerait alors quelque chose qu'il n'a jamais vu.
 */
export function setOutfit(outfit: OutfitIn): void {
  declaredOutfit = outfit;
}

export function getOutfit(): OutfitIn | null {
  return declaredOutfit;
}

/**
 * Le moment choisi, sous forme d'empreinte.
 *
 * L'analyse évalue l'adéquation de chaque pièce **au moment** : elle en dépend
 * donc, et sa clé d'idempotence doit le contenir. Sans cela, revenir en arrière
 * pour choisir une autre occasion renvoie l'analyse précédente, figée sur la
 * première, et la décision répète la même recommandation.
 */
export function setMoment(moment: string): void {
  declaredMoment = moment;
}

export function getMoment(): string | null {
  return declaredMoment;
}
