// Title first, key second: the title is the primary text (cut to TITLE_MAX,
// the full text on hover) and the key follows it, small and muted.
import { truncate } from '../lib/display.ts';
import type { Titles } from '../lib/titles.ts';

export function KeyTag({ value }: { value: string }) {
  return <span className="key">{value}</span>;
}

export function TitleText({ title }: { title: string }) {
  const short = truncate(title);
  return (
    <span className="title-text" title={short.truncated ? title : undefined}>
      {short.text}
    </span>
  );
}

// A title with its key after it.
export function Titled({ title, itemKey }: { title: string; itemKey: string }) {
  return (
    <>
      <TitleText title={title} /> <KeyTag value={itemKey} />
    </>
  );
}

// A reference to another record: "title (key)".
export function TitleRef({ title, itemKey }: { title: string; itemKey: string }) {
  return (
    <>
      <TitleText title={title} /> <KeyTag value={`(${itemKey})`} />
    </>
  );
}

// For a link that only has a key: "title (key)", or the key alone when its
// title is unknown.
export function KeyLabel({ itemKey, titles }: { itemKey: string; titles: Titles }) {
  const title = titles.get(itemKey);
  if (title === undefined) {
    return <KeyTag value={itemKey} />;
  }
  return <TitleRef title={title} itemKey={itemKey} />;
}
