# IP of Webby-Soft SRL.
# Subsets the design's Nioicon font to the glyphs the U33 public site uses.
# Usage: uv run --no-project --with fonttools --with brotli python -I subset-nioicon.py \
#          <nioicons.woff> <out.woff2>
# Glyphs: the seven the design pages use (e93b arrow, e97d building, e9be check, e9e9 clock,
# ea06 cross, ead5 lock, eb75 gear) and the ones the React port adds for live data
# (ea50 file-text: receivables/invoices, ec33 user: guarantees, eb7c shield-check: other
# security, e9f4 coins: cash collateral, e9b8 check-circle / e90d alert-circle: toasts).
import sys

from fontTools import subset

GLYPHS = [
    0xE93B, 0xE97D, 0xE9BE, 0xE9E9, 0xEA06, 0xEAD5, 0xEB75,
    0xEA50, 0xEC33, 0xEB7C, 0xE9F4, 0xE9B8, 0xE90D,
]

src, out = sys.argv[1], sys.argv[2]
options = subset.Options()
options.flavor = "woff2"
options.layout_features = []
options.name_IDs = ["*"]
options.notdef_outline = True
options.drop_tables += ["DSIG"]
font = subset.load_font(src, options)
subsetter = subset.Subsetter(options)
subsetter.populate(unicodes=GLYPHS)
subsetter.subset(font)
subset.save_font(font, out, options)
print("wrote", out, len(GLYPHS), "glyphs")
