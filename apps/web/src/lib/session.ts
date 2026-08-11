/**
 * Persistance minimale du parcours.
 *
 * On ne garde que l'identifiant de session : tout le reste se relit auprès de
 * l'API via `GET /sessions/{id}`. Un rafraîchissement de page ne perd donc
 * jamais la décision — et le frontend ne détient aucune copie divergente de
 * l'état officiel.
 */

const KEY = "mirror-ops.session";

export function saveSessionId(id: string): void {
  try {
    window.sessionStorage.setItem(KEY, id);
  } catch {
    /* navigation privée : le parcours reste valable pour l'onglet en cours */
  }
}

export function readSessionId(): string | null {
  try {
    return window.sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function clearSession(): void {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

/** Clé d'idempotence stable par étape : un double-clic ne consomme pas deux unités. */
export function stepKey(sessionId: string, step: string): string {
  return `${sessionId}:${step}`;
}

/**
 * Empreinte courte et stable d'un jeu d'entrées.
 *
 * La clé d'idempotence doit couvrir ce que l'utilisateur a saisi, pas seulement
 * l'étape : sans cela, revenir en arrière pour corriger sa tenue puis relancer
 * renvoie l'analyse précédente, et la correction reste sans effet. Deux clics
 * sur des entrées identiques gardent la même clé — la protection reste entière.
 */
export function fingerprint(...parts: (string | number | undefined)[]): string {
  const text = parts.filter((p) => p !== undefined).join("|");
  let hash = 5381;
  for (let i = 0; i < text.length; i += 1) {
    hash = ((hash << 5) + hash + text.charCodeAt(i)) >>> 0;
  }
  return hash.toString(36);
}
