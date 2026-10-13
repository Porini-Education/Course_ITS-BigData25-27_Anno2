# EDA

The investigation phase before modelling or analysis.

> Imagine someone gives you a CSV file and asks you to build a dashboard, a machine learning model, or answer a business question. 

The first thing you should not do is start building. You need to understand what is inside the data. 

That understanding process is called Exploratory Data Analysis, or EDA.

## 1. What is EDA?

EDA is the process of examining, visualising, and questioning a dataset to understand its structure, quality, patterns, and potential issues.

EDA is detective work, not reporting.

EDA tries to answer questions such as:
- What data do I have?
- Is the data complete?
- Can I trust it?
- What looks unusual?
- What relationships exist?
- What should I investigate further?

## 2. Why do EDA?

```
Data
 ↓
EDA
 ↓
Cleaning
 ↓
Analysis / ML / Reporting
 ↓
Decisions
```

Without EDA you risk:

- Building models on bad data
- Creating misleading reports
- Drawing incorrect conclusions
- Missing important patterns

> Most data science failures are data understanding failures.

## 3. The Five Questions of EDA

### Question 1: What does the dataset look like?

Check:
- Rows
- Columns
- Data types
- Sample records

Example:

```python
df.head()
df.info()
df.shape
```

Goal:
- Develop a mental model of the data.

### Question 2: Is the data healthy?

Look for:
- Missing values
- Duplicates
- Invalid values
- Data type problems

Example:

```python
df.isnull().sum()
df.duplicated().sum()
```

Goal:
- Determine whether the data can be trusted.

### Question 3: What are the distributions?

For numerical columns:
- Mean
- Median
- Min / Max
- Histograms

Example:

```python
df.describe()
```

For categorical columns:
- Value counts
- Bar plots

Example:

```python
df['categorical_column'].value_counts()
```

For text columns:
- Length of text
- Unique values
- Word frequency

Example:

```python
df['text_column'].str.split().explode().value_counts()
```
Visuals:
- Histogram
- Boxplot
- Violin plot

Discuss:
- Skewness
- Long tails
- Outliers

### Question 4: What relationships exist?

Examples:
- Sales vs profit
- Age vs income
- Quantity vs revenue

Visuals:
- Scatter plots
- Correlation matrix

Goal:
- Find variables that move together.

### Question 5: What surprises us?

This is the most important step where analysts create value.

Ask:
- Are there unusual clusters?
- Unexpected trends?
- Strange records?
- Business insights?

## 4. Typical EDA deliverables

An EDA report usually contains:

| Area | Examples |
| --- | --- |
| Dataset overview | Row count, column count |
| Data quality | Missing values, duplicates |
| Statistics | Mean, median, spread |
| Visualisations | Histograms, box plots |
| Relationships | Correlations |
| Findings | Key observations |
| Next actions | Cleaning, feature engineering |

## 5. Mini EDA Framework

**SCAN**:
- Structure
- Cleanliness
- Anomalies
- Networks (relationships)

Whenever you get a new dataset:
- Understand structure
- Check quality
- Find anomalies
- Explore relationships

> Your goal isn't to build a model from the data you have. Your goal is to become the expert on that dataset.