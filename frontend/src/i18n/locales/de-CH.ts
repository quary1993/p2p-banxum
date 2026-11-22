// IP of Webby-Soft SRL.
/*
 * Swiss Standard German messages of the investor platform (plan/22 U33-DEC-31): "Sie", no "ß",
 * simple, formal and welcoming. The keys are the English texts of t().
 *
 * - de-CH.design.json: the approved German texts of the U33 design (its BXM_DE dictionary), with
 *   the design's numbered placeholders renamed to ours.
 * - de-CH.drafts.json: texts the design does not contain, drafted for the same tone. They need a
 *   native-speaker review before launch (plan/22).
 *
 * catalog.test.ts checks that every t() text of the investor area has an entry, that placeholders
 * match and that no "ß" is used.
 */
import type { Messages } from "../index";
import design from "./de-CH.design.json";
import drafts from "./de-CH.drafts.json";

const messages: Messages = { ...design, ...drafts };

export default messages;
