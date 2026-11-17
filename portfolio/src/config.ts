// Personal details are PLACEHOLDERS. Set them via environment variables at build time
// (VITE_OWNER_NAME, VITE_CONTACT_EMAIL, VITE_GITHUB_URL, VITE_LINKEDIN_URL, VITE_*_DEMO_URL, ...).
// Any value left unset renders as "not configured" -- the site never shows a fake live link.
const env = import.meta.env;

export interface LinkValue { url: string | null; label: string }
const link = (value: string | undefined, label: string): LinkValue => ({ url: value && value.trim() ? value.trim() : null, label });

export const site = {
  ownerName: env.VITE_OWNER_NAME?.trim() || "Your Name",
  ownerNameIsPlaceholder: !env.VITE_OWNER_NAME?.trim(),
  headline: "AI Engineer -- production LLM systems: RAG, agents, safe text-to-SQL and evaluation",
  location: env.VITE_OWNER_LOCATION?.trim() || null,
  email: link(env.VITE_CONTACT_EMAIL, "Email"),
  github: link(env.VITE_GITHUB_URL, "GitHub"),
  linkedin: link(env.VITE_LINKEDIN_URL, "LinkedIn"),
  resume: link(env.VITE_RESUME_URL, "Resume"),
  siteUrl: env.VITE_SITE_URL?.trim() || null,
};

// Monorepo support: when VITE_MONOREPO_URL is set (all projects in one repository), each project's
// repository link and documentation links point at its folder in that repository.
const mono = env.VITE_MONOREPO_URL?.trim().replace(/\/$/, "") || null;
const repoLink = (explicit: string | undefined, slug: string): LinkValue =>
  link(explicit?.trim() || (mono ? `${mono}/tree/main/${slug}` : undefined), "GitHub repository");

export const projectLinks: Record<string, { demo: LinkValue; repo: LinkValue }> = {
  "nexus-ai": { demo: link(env.VITE_NEXUS_DEMO_URL, "Live demo"), repo: repoLink(env.VITE_NEXUS_REPO_URL, "nexus-ai") },
  "datawise-ai": { demo: link(env.VITE_DATAWISE_DEMO_URL, "Live demo"), repo: repoLink(env.VITE_DATAWISE_REPO_URL, "datawise-ai") },
  "evalops-ai": { demo: link(env.VITE_EVALOPS_DEMO_URL, "Live demo"), repo: repoLink(env.VITE_EVALOPS_REPO_URL, "evalops-ai") },
};

export function docUrl(project: string, path: string): string | null {
  const kind = path.endsWith("/") ? "tree" : "blob";
  if (mono) return `${mono}/${kind}/main/${project}/${path.replace(/\/$/, "")}`;
  const repo = projectLinks[project]?.repo.url;
  return repo ? `${repo.replace(/\/$/, "")}/${kind}/main/${path.replace(/\/$/, "")}` : null;
}
