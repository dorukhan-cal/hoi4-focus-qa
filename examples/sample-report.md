# Focus tree QA report

Scanned **1** file(s): 1 tree(s), 19 focus(es).

**2 error(s), 5 warning(s), 0 info**

| Severity | Check | Focus | Location | Detail |
| --- | --- | --- | --- | --- |
| error | missing-icon | `CON_epsilon` | `content.txt:57` | icon 'GFX_con_undeclared' is not declared in any .gfx file -- a placeholder will be shown |
| error | missing-localisation | `CON_gamma` | `content.txt:37` | no english key 'CON_gamma' -- the raw key will be shown in game |
| warning | infrastructure-without-bypass | `CON_infra_dynamic` | `content.txt:235` | entire reward is infrastructure construction in a dynamically selected scope, and there is no bypass -- the focus completes with no effect once that infrastructure is at the cap |
| warning | infrastructure-without-bypass | `CON_infra_no_bypass` | `content.txt:149` | entire reward is infrastructure construction in states 11, 12, and there is no bypass -- the focus completes with no effect once that infrastructure is at the cap |
| warning | missing-description | `CON_delta` | `content.txt:47` | no english key 'CON_delta_desc' -- the focus has no description text |
| warning | position-collision | `CON_overlap_b` | `content.txt:296` | shares grid position x=14 y=0 with 'CON_overlap_a' (content.txt:287) |
| warning | position-collision | `CON_stub_b` | `content.txt:136` | shares grid position x=16 y=0 with 'CON_stub_a' (content.txt:121) |

