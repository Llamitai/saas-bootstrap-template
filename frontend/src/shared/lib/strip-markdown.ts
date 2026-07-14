export function stripMarkdown(input: string | null | undefined): string {
  if (!input) return "";
  return input
    .replace(/```[\s\S]*?```/g, (match) => match.replace(/```\w*\n?|```/g, ""))
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/(\*\*|__)(.*?)\1/g, "$2")
    .replace(/(\*|_)(.*?)\1/g, "$2")
    .replace(/~~(.*?)~~/g, "$1")
    .replace(/^\s{0,3}(#{1,6}\s+|>\s+|[-*+]\s+|\d+\.\s+)/gm, "")
    .replace(/<\/?[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
