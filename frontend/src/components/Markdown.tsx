import ReactMarkdown from "react-markdown";

/** Inline-only Markdown: bold, emphasis and code survive, everything else is unwrapped. */
export function Markdown({ text, className = "" }: { text: string; className?: string }) {
  if (!text) return null;
  return (
    <ReactMarkdown
      allowedElements={["p", "strong", "em", "code"]}
      unwrapDisallowed
      components={{
        p: ({ children }) => <span className={className}>{children}</span>,
        code: ({ children }) => <code className="font-mono text-[0.9em]">{children}</code>,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}
