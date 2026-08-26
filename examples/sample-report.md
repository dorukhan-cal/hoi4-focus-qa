# Focus tree QA report

Scanned **1** file(s): 1 tree(s), 11 focus(es).

**5 error(s), 3 warning(s), 1 info**

| Severity | Check | Focus | Location | Detail |
| --- | --- | --- | --- | --- |
| error | dangling-prerequisite | `TST_expeditionary_force` | `testland.txt:67` | prerequisite references unknown focus 'TST_colonial_office' |
| error | dangling-relative-position | `TST_home_defence` | `testland.txt:126` | relative_position_id references unknown focus 'TST_coastal_command' |
| error | duplicate-id | `TST_rearmament` | `testland.txt:16` | focus id defined 2 times (testland.txt:16, testland.txt:139) |
| error | prerequisite-cycle | `TST_first_congress` | `testland.txt:103` | prerequisite loop: TST_first_congress -> TST_second_congress -> TST_first_congress |
| error | unreachable | `TST_combined_arms` | `testland.txt:54` | requires both 'TST_land_doctrine' and 'TST_naval_doctrine', which are mutually exclusive |
| warning | asymmetric-exclusivity | `TST_land_doctrine` | `testland.txt:28` | excludes 'TST_naval_doctrine', but 'TST_naval_doctrine' does not exclude it back (testland.txt:41) -- the block only applies in one direction |
| warning | no-completion-reward | `TST_war_economy` | `testland.txt:79` | focus has no completion_reward, so completing it does nothing |
| warning | position-collision | `TST_total_mobilisation` | `testland.txt:88` | shares grid position x=10 y=1 with 'TST_war_economy' (testland.txt:79) |
| info | no-bypass | `TST_total_mobilisation` | `testland.txt:88` | focus is gated by 'available' but has no 'bypass' -- confirm it should not auto-complete when its purpose is already achieved |

