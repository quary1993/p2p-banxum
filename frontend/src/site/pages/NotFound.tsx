// IP of Webby-Soft SRL.
// Page not found (design: pages_home.js notFound()), for every unknown address: the bad URL
// stays in the address bar.
import { PageHead, SiteLink } from "../components";

export function NotFound() {
  return (
    <PageHead
      actions={
        <>
          <SiteLink className="btn btn-lg btn-primary" href="/">
            Home
          </SiteLink>
          <SiteLink className="btn btn-lg btn-site-outline" href="/projects">
            Projects
          </SiteLink>
        </>
      }
      eyebrow="404"
      lead="The link may be old, or the project may have been removed."
      title="This page does not exist"
    />
  );
}
