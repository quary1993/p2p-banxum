// IP of Webby-Soft SRL.
// Nioicon glyph as the design writes it: <em class="icon ni ni-NAME">. Only glyphs kept in the
// generated u33.css subset render (see tools/u33-design/README.md); decorative unless a label is given.
export function NiIcon({ name, label, className = "" }: { name: string; label?: string; className?: string }) {
  return label ? (
    <em aria-label={label} className={`icon ni ni-${name} ${className}`.trim()} role="img" />
  ) : (
    <em aria-hidden="true" className={`icon ni ni-${name} ${className}`.trim()} />
  );
}
