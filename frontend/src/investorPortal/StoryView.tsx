import { Fragment, type ReactNode } from "react";
import { storyImageUrl, type StoryDocument, type StoryRun } from "./story";

function renderRun(run: StoryRun, key: number): ReactNode {
  const lines = run.text.split("\n");
  let node: ReactNode = lines.map((line, index) => (
    <Fragment key={index}>
      {index > 0 ? <br /> : null}
      {line}
    </Fragment>
  ));
  if (run.bold) node = <strong>{node}</strong>;
  if (run.italic) node = <em>{node}</em>;
  if (run.href) {
    node = (
      <a href={run.href} rel="noopener noreferrer nofollow" target="_blank">
        {node}
      </a>
    );
  }
  return <Fragment key={key}>{node}</Fragment>;
}

export function StoryRuns({ runs }: { runs: StoryRun[] }) {
  return <>{runs.map((run, index) => renderRun(run, index))}</>;
}

/**
 * Read-only renderer for investor stories. Builds React elements from the
 * validated block document only; there is no HTML pass-through anywhere.
 */
export function StoryView({ story, imageUrl = storyImageUrl }: { story: StoryDocument; imageUrl?: (imageId: string) => string }) {
  return (
    <div className="story">
      {story.blocks.map((block, index) => {
        switch (block.type) {
          case "paragraph":
            return (
              <p className="story-p" key={index}>
                <StoryRuns runs={block.runs} />
              </p>
            );
          case "heading":
            return block.level === 3 ? (
              <h3 className="story-h3" key={index}>
                <StoryRuns runs={block.runs} />
              </h3>
            ) : (
              <h2 className="story-h2" key={index}>
                <StoryRuns runs={block.runs} />
              </h2>
            );
          case "quote":
            return (
              <blockquote className="story-quote" key={index}>
                <StoryRuns runs={block.runs} />
              </blockquote>
            );
          case "bullet_list":
            return (
              <ul className="story-list" key={index}>
                {block.items.map((item, itemIndex) => (
                  <li key={itemIndex}>
                    <StoryRuns runs={item} />
                  </li>
                ))}
              </ul>
            );
          case "numbered_list":
            return (
              <ol className="story-list" key={index}>
                {block.items.map((item, itemIndex) => (
                  <li key={itemIndex}>
                    <StoryRuns runs={item} />
                  </li>
                ))}
              </ol>
            );
          case "image":
            return (
              <figure className="story-figure" key={index}>
                <img alt={block.alt} className="story-img" decoding="async" loading="lazy" src={imageUrl(block.image_id)} />
                {block.caption ? <figcaption className="story-caption">{block.caption}</figcaption> : null}
              </figure>
            );
          case "divider":
            return <hr className="story-hr" key={index} />;
          default:
            return null;
        }
      })}
    </div>
  );
}
