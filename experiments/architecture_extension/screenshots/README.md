# Cloud Browser visualisation check

On 27 September 2026, the `aspic-view/1` file at
[`../results/aspic-view.json`](../results/aspic-view.json) was imported through
**Import snapshot** in the Vue/TypeScript app from
[`emmett08/aspic_visualisation`](https://github.com/emmett08/aspic_visualisation)
at commit `37c89066a4eaff4a574f534950f4cd7723c26e2f`. The local Cloud Browser
preview was `http://terminal.local:4173/`. This was a UI rendering check, not a
new collection or independent formal assessment.

Input file SHA-256: `c2bed1273086b62b7719df4c61372d62190c9ad52fdc5a5f5b5e9667dab75567`.
Its source digest is `abdbe61fa7ff300ea01a841ad97a61ded47b3233ff1b03b8eed595cfe07a21b7`
and its snapshot digest is `646377611e61428dccc4a87255fca6797f2a8b28c114b9dee574b8468ed54687`.

- [`paired-tie-1790513118711.jpg`](paired-tie-1790513118711.jpg) shows
  `local_check_tie` accepted, 25 constructed arguments (24 in, one out), and
  the selected `paired_tie` route. SHA-256:
  `7838918dd81d0948ac02597080b3011048f942ca83f9e72499442182f07f52d7`.
- [`debt-undercut-1790513167512.jpg`](debt-undercut-1790513167512.jpg)
  shows `future_debt_reduced` out and the `debt_not_measured` undercut
  `A23 → A21`; two unavailable dispatch-failure evidence declarations are
  visible. SHA-256:
  `9f75eb4da4adbc69076339516080ec11d8b57d9826353fa22b91460f81ce3e29`.

The browser also showed the imported snapshot event. UI labels are relative to
the supplied assessment. The app does not authenticate that source or the
underlying coding sessions.
