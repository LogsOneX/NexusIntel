# Graph UX QA

## Manual Checks
1. Open `/graph` with an investigation.
2. Verify the Google Studio graph shell remains full-screen with no permanent side columns.
3. Select one node and confirm inspector + node popover behavior still works.
4. Multi-select nodes with Ctrl/Cmd/Shift click.
5. Use Select Neighbors and verify adjacent nodes are added to selection.
6. Hide selected nodes, then Show All.
7. Toggle candidate leads and verify candidate-like nodes appear/disappear.
8. Toggle signals and verify signal-like nodes appear/disappear.
9. Move confidence filter and verify low-confidence nodes are hidden.
10. Use minimap for orientation; dots should reflect visible nodes only.
11. Run a transform from a node popover; verify `/api/v1/transforms/run` is used and telemetry opens.
12. Verify graph does not reintroduce Cytoscape rectangle nodes or old toolbar classes.

## Roadmap QA
- Lasso selection
- Edge context menu
- Undo/redo layout operations
- Server-side layout save/restore
- Cluster expand/collapse
