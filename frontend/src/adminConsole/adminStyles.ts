// IP of Webby-Soft SRL.
// The admin console's stylesheet (audit G-07, S7): styles.css is loaded with the lazy admin area only.
// The investor area (U33, html.bxu) and the public site (html.bxs / html.bxp) never load it.
// Audit S4-9: the build puts every rule of styles.css below :where(html.bxa) (adminCssScope.ts), and
// AdminSkin sets that class only while the admin console is mounted. So the stylesheet, which stays in
// the page after a route change, styles nothing outside the admin console.
import "../styles.css";
