// IP of Webby-Soft SRL.
/*
 * About: who runs Banxum, regulation, company details, how money is protected, team (design:
 * pages_more.js about()). Company details come from content.ts (siteCompany); the team cells
 * are the design's placeholders until the owner provides names and photos.
 */
import type { ReactNode } from "react";

import { Eyebrow, Flag, NiIcon, PageHead, SiteLink } from "../components";
import { siteCompany } from "../content";

const TEAM_ROLES = ["Chief executive officer", "Head of credit", "Compliance officer", "Head of partnerships"];

function ProofCell({ mark, title, children }: { mark: string; title: string; children: ReactNode }) {
  return (
    <div>
      <span className="site-proof-mark">{mark}</span>
      <h3 className="site-h4">{title}</h3>
      <p className="site-text mb-0">{children}</p>
    </div>
  );
}

function ProtectionCell({ index, title, children }: { index: string; title: string; children: ReactNode }) {
  return (
    <div>
      <div className="site-cell-top">
        <span>{index}</span>
      </div>
      <h3 className="site-h4">{title}</h3>
      <p className="site-text mb-0">{children}</p>
    </div>
  );
}

export function About() {
  const co = siteCompany;
  return (
    <>
      <PageHead
        actions={
          <>
            <SiteLink className="btn btn-lg btn-primary" href="/register">
              Open account
            </SiteLink>
            <SiteLink className="btn btn-lg btn-site-outline" href="/contact">
              Contact us
            </SiteLink>
          </>
        }
        eyebrow={
          <>
            <Flag code="CH" label="Switzerland" />
            About Banxum
          </>
        }
        lead={`Banxum® is a registered trademark. The platform is owned and operated by ${co.name}, a Swiss financial company: affiliated to VQF and FINOS, audited every year, with ${co.capital} of share capital.`}
        title="Swiss-regulated financial platform"
      />
      <section className="site-section">
        <div className="site-wrap">
          <div className="site-section-head">
            <div>
              <Eyebrow>Regulated in Switzerland</Eyebrow>
              <h2 className="site-h2">Supervised, audited, capitalised</h2>
            </div>
            <p className="site-text mb-0">What stands behind the company that holds your wallet and collects your repayments.</p>
          </div>
          <div className="site-cells is-4">
            <ProofCell mark="VQF" title="Member of VQF">
              The self-regulatory organisation recognised by FINMA supervises Garanta&apos;s financial activities and its
              anti-money-laundering duties.
            </ProofCell>
            <ProofCell mark="FINOS" title="Affiliated to FINOS">
              The Swiss financial ombudsman mediates free of charge if you disagree with us.
            </ProofCell>
            <ProofCell mark="Audited" title="Audited data">
              Garanta&apos;s accounts and the platform&apos;s data are audited every year by an independent auditor.
            </ProofCell>
            <ProofCell mark="CHF 1.1m" title="Share capital">
              {co.capital} of share capital.
            </ProofCell>
          </div>
        </div>
      </section>
      <section className="site-section">
        <div className="site-wrap site-split">
          <div>
            <Eyebrow>The company</Eyebrow>
            <h2 className="site-h2">{co.name}</h2>
            <p className="site-lead mt-4">
              A Swiss financial company limited by shares. It owns and operates the Banxum platform and signs the
              agreements with borrowers, loan originators and investors.
            </p>
          </div>
          <dl className="site-kv">
            <div>
              <dt>Banxum®</dt>
              <dd>Registered trademark; platform owned and operated by Garanta</dd>
            </div>
            <div>
              <dt>Address</dt>
              <dd>
                {co.street}
                <br />
                {co.city}
              </dd>
            </div>
            <div>
              <dt>UID and VAT</dt>
              <dd>{co.uid}</dd>
            </div>
            <div>
              <dt>LEI</dt>
              <dd>{co.lei}</dd>
            </div>
            <div>
              <dt>Share capital</dt>
              <dd>{co.capital}</dd>
            </div>
            <div>
              <dt>Self-regulatory organisation</dt>
              <dd>VQF · {co.vqf}</dd>
            </div>
            <div>
              <dt>Ombudsman</dt>
              <dd>FINOS, Finanzombudsstelle Schweiz</dd>
            </div>
            <div>
              <dt>Auditor</dt>
              <dd>{co.auditor}</dd>
            </div>
          </dl>
        </div>
      </section>
      <section className="site-section is-paper">
        <div className="site-wrap">
          <div className="site-section-head is-single">
            <div>
              <Eyebrow>Protection</Eyebrow>
              <h2 className="site-h2">How your money is protected</h2>
            </div>
          </div>
          <div className="site-cells is-4">
            <ProtectionCell index="01" title="Your wallet">
              A segregated wallet in your name, with a CHF and a EUR balance, kept apart from Garanta&apos;s own money. It
              earns no interest and goes back to your bank after 58 days if you do not invest.
            </ProtectionCell>
            <ProtectionCell index="02" title="Your claims">
              Each share is assigned to you with a qualified electronic signature. Garanta collects the repayments as agent
              for the investors and enforces the security if needed.
            </ProtectionCell>
            <ProtectionCell index="03" title="Your account">
              Access your account with a magic link sent to your email. Investments, withdrawals and new bank accounts ask
              for an extra code and your PIN code.
            </ProtectionCell>
            <ProtectionCell index="04" title="Continuity">
              The claims you bought are assigned to you. If Garanta could no longer collect them, the agreements pass the
              collection to another agent or to the investors; this can delay repayments.{" "}
              <SiteLink href="/legal/risk">Risk information</SiteLink>
            </ProtectionCell>
          </div>
        </div>
      </section>
      <section className="site-section">
        <div className="site-wrap">
          <div className="site-section-head is-single">
            <div>
              <Eyebrow>Team</Eyebrow>
              <h2 className="site-h2">The people behind the loans</h2>
            </div>
          </div>
          <div className="site-cells is-4">
            {TEAM_ROLES.map((role) => (
              <div key={role}>
                <div className="site-photo">
                  <NiIcon name="ni-user" />
                  <span>Photo · team</span>
                </div>
                <h3 className="site-h4">Name to be added</h3>
                <p className="site-small mb-0">{role}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
