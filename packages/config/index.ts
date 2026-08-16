/**
 * Constantes produit partagées.
 *
 * Le libellé d'une occasion ou d'un objectif appartient au produit, pas au
 * moteur : le backend renvoie des identifiants stables, l'interface décide de
 * la façon de les nommer à l'utilisateur.
 */

/**
 * Positionnement produit — source de vérité unique.
 *
 * MIRROR OPS est un *moteur de décision d'apparence contextuel*. Ce n'est ni un
 * styliste, ni un assistant d'achat, ni un générateur de tenues. La distinction
 * qui compte n'est pas « Skin AI + VTO » : c'est CHECK ≠ DECIDE.
 *
 * Vérifier son look, c'est constater. MIRROR OPS décide de ce qui mérite d'être
 * changé — ou décide qu'il n'y a rien à changer.
 */
export const PRODUCT = {
  name: "MIRROR OPS",
  category: "Contextual appearance decision engine",
  signature: "Fit the moment. One change.",
  promise: "Don't redesign your look. Fix the mismatch.",
  /** La question qui distingue le produit de tout ce qui l'entoure. */
  question: "Will this look work here?",
  closing: "One change. That's all you needed.",
  /** Ce que doit retenir un jury en une phrase. */
  oneLiner:
    "Mirror Ops decides whether your look fits the moment you're about to enter — and when it doesn't, finds the ONE change worth making and proves it before you act.",
} as const;

export const OCCASION_LABELS: Record<string, string> = {
  interview: "Interview",
  presentation: "Presentation",
  date: "Date",
  business: "Business",
  event: "Event",
  wedding: "Wedding",
  conference: "Conference",
  dinner: "Dinner",
  travel: "Travel",
  other: "Something else",
};

export const GOAL_LABELS: Record<string, string> = {
  confident: "Confident",
  professional: "Professional",
  approachable: "Approachable",
  elegant: "Elegant",
  expressive: "Expressive",
};

export const TIME_LABELS: Record<string, string> = {
  "<5m": "Under 5 min",
  "5_15m": "5–15 min",
  "15_30m": "15–30 min",
  "30m_plus": "30 min or more",
};

export const ELEMENT_LABELS: Record<string, string> = {
  jacket: "Jacket",
  top: "Top",
  bottom: "Bottom",
  shoes: "Shoes",
  accessories: "Accessories",
  colour: "Colour balance",
};

export const DIMENSION_LABELS: Record<string, string> = {
  professional_presence: "Professional presence",
  visual_coherence: "Visual coherence",
  confidence_proxy: "Confidence",
  approachability: "Approachability",
  expressiveness: "Expressiveness",
  elegance: "Elegance",
};

/** Les trois dimensions montrées sur l'écran Before / After (Doc 03 §13). */
export const HEADLINE_DIMENSIONS = [
  "professional_presence",
  "visual_coherence",
  "confidence_proxy",
] as const;

/**
 * Ce que MIRROR OPS n'est pas. Conservé dans le code, et non seulement dans un
 * document, parce que la contrainte EST le produit : toute fonctionnalité qui
 * ferait glisser l'interface vers l'une de ces catégories doit être retirée.
 */
export const NOT_THIS = [
  "AI stylist — « here are 20 outfits »",
  "Shopping agent — « here are products to buy »",
  "Wardrobe manager — « here is your digital closet »",
  "Virtual try-on app — « try these clothes »",
  "Skin diagnosis tool — « here is what's wrong with your skin »",
  "Purchase optimizer — « which product is better »",
] as const;

/** Les trois verdicts d'adéquation, dans le vocabulaire du produit. */
export const FIT_LABELS: Record<string, string> = {
  FIT: "Fits the moment",
  ALMOST_THERE: "Almost there",
  MISMATCH: "Doesn't fit the moment",
};

/**
 * À quel point la tenue est habillée.
 *
 * Une seule question, trois réponses — et c'est elle qui permet au produit de
 * juger différemment un mariage et un voyage. Sans elle, les dix occasions
 * rendent le même verdict : la thèse est vraie mais invisible.
 */
export const DRESS_LEVELS = [
  { value: 0.22, label: "Casual", hint: "jeans, sneakers, no jacket" },
  { value: 0.55, label: "In between", hint: "smart casual" },
  { value: 0.88, label: "Dressed up", hint: "tailored, formal shoes" },
] as const;

export const FLOW_STEPS = [
  { path: "/moment", label: "Moment" },
  { path: "/look", label: "Look" },
  { path: "/one-change", label: "One change" },
  { path: "/compare", label: "Proof" },
] as const;
