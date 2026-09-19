# F1 Tyre Strategy Intelligence System

This project focuses on building an intelligent Formula 1 tyre strategy simulation and prediction system using FastF1 race data, machine learning, and future AI-assisted strategy reasoning.

The project originally started as a stint-length prediction model using 2023 Formula 1 race data. Over time, it evolved into a larger strategy simulation framework capable of predicting realistic tyre stints, generating complete race strategies, estimating pit windows, and comparing strategic approaches across different races and compounds.

The long-term objective is to develop a complete hybrid motorsport intelligence system where machine learning handles structured numerical prediction while AI models provide strategic reasoning, explanation, and interaction.

---

## Project Status

Phase 1 of the project has been completed successfully.

The current system is capable of:
- Predicting tyre stint lengths using machine learning
- Simulating complete race strategies sequentially
- Generating pit windows
- Comparing different strategic combinations
- Running independently outside Jupyter notebooks using a modular Python architecture

The project has now transitioned into Phase 2, where the focus is on expanding the dataset, improving contextual awareness, and preparing the foundation for AI-assisted strategy analysis.

---

## Dataset and Data Engineering

The dataset is built entirely using FastF1 race telemetry and session data.

The original 2023 workflow included:
- Race data extraction
- Weather data collection
- Lap-level cleaning and preprocessing
- Weather-driver data merging
- Stint-level transformation

The project is now expanding into a reusable multi-season pipeline, beginning with 2024 season integration.

Each season is processed independently before final model-ready datasets are merged. This keeps the workflow modular, reproducible, and easier to debug.

Current datasets include:
- Raw race data
- Cleaned race data
- Weather datasets
- Merged weather-race datasets
- Stint-level datasets

---

## Machine Learning Model

The current prediction model is based on Ridge Regression using OneHotEncoding for categorical features.

The model predicts:
- Expected tyre stint length

Current model inputs:
- Grand Prix
- Tyre Compound
- Stint Number
- Interaction features between race context and stint phase

Feature engineering currently includes:
- GP_Stint
- Compound_Stint

The latest version of the model achieves an MAE of approximately 5.95 laps.

The model captures:
- Circuit-specific tyre behavior
- Compound-dependent degradation trends
- Variation across different race phases

---

## Strategy Simulation Engine

The project now includes a complete strategy simulation layer built on top of the ML model.

The simulator:
- Predicts stints sequentially
- Maintains total race lap budget
- Simulates multi-stop strategies
- Generates pit windows
- Compares valid strategic combinations
