# Open PitSense

Double-click **Start Dashboard.cmd** in this folder.

While running, open **http://127.0.0.1:8501**.

Choose a race, choose tyre compounds, and explore the chart. Use **Compare strategies** to compare pit-stop plans. Download results using the JSON/CSV buttons.

The launcher sets up the Python environment if needed. Install Python 3.12 first. For detailed command-line, data-processing, training and troubleshooting instructions, read **README.md**.

For real API data, open **Live Race Centre** in the sidebar. Historical session snapshots and current circuit weather work without credentials. Live car telemetry requires an OpenF1 access token; see **docs/LIVE_DATA.md**.

Open **Race Time Optimizer** to compare simulated race times and adjust pit laps. Its editable defaults are illustrative, not calibrated race predictions. The original strategy explorer ranks by stint balance.
