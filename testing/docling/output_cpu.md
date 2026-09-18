<!-- image -->

CLARISYNC

## Use Case Risk Recategorization

Ryef Taimur, Ibrahim Murtaza

## 1 Purpose

Company and client information is regularly sent to commercial LLM providers when employees use tools like ChatGPT for work tasks, with no control over where that information goes. This document classifies every Phase 1 use case by risk using two dimensions, so the highest exposure use cases are identified and given the right level of care.

## 2 Categories

Every use case is placed into one of six categories, based on the kind of work it does rather than the topic it touches, so it can be scanned and compared consistently across the document.

- Coding
- QA and Testing
- Documentation
- Data Sorting and Analysis
- Rephrasing and Drafting
- Security and Risk Review

## 3 Risk Dimensions

## 3.1 Impact

Impact signifies what we gave the model. It reflects the sensitivity of the input itself, and whether that sensitivity is compounded by the fact that there is currently no generic, controlled platform in place, meaning inputs go to tools that retain and may train on them by default, with no control over how that data is used afterward.

| Level   | What it means                                                                                                                                        | Why it gets this level                                                                                                                                                                                                                                                                                                |
|---------|------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Low     | The input has nothing in it beyond what could be shared freely with anyone outside the company.                                                      | Even though the tool may retain the input, there is nothing sensitive being retained, so there is nothing here that could harm the business, even in the worst case.                                                                                                                                                  |
| Medium  | The input has real internal business information that is not public, but is also not uniquely valuable, such as internal reports or process details. | If this is retained or used for training with no control over its future use, it would cause real but recoverable trouble, such as embarrassment or friction, not lasting damage.                                                                                                                                     |
| High    | The input has proprietary or private information, such as source code, system design, trade secrets, or another company's confidential data.         | Because there is no controlled platform, this input may be retained or trained on indefinitely. This is not a one time exposure, it is a permanent loss of control over that information, and it could seriously harm the business, hurt a client relationship, or create legal trouble that cannot easily be undone. |

## 3.2 Fallout

Fallout tells us what happens if the model gives a wrong answer and nobody catches it. Unlike Impact, this has nothing to do with what was shared, it is only about what happens after the answer is given, so a use case with completely harmless input can still cause real damage if a confident but wrong answer gets trusted and acted on without anyone reviewing it first.

<!-- image -->

CLARISYNC

<!-- image -->

CLARISYNC

| Level   | What it means                                                                                                                            | Why it gets this level                                                                                                                                           |
|---------|------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Low     | A wrong answer is either obvious right away, or it does not lead to anything serious even if nobody catches it.                          | There is no real path from a wrong answer to actual harm. The mistake shows itself, or it simply does not matter enough to act on.                               |
| Medium  | A wrong answer causes wasted time or extra work, but someone eventually catches it before it goes further.                               | The cost is real, but it stays contained. It costs effort, not money, safety, or trust.                                                                          |
| High    | A wrong answer could be acted on before anyone checks it, and that action leads to a real financial, security, legal, or client problem. | This is the case where a wrong answer, if nobody catches it, causes real and sometimes lasting harm, such as a bad decision, a leaked issue, or a legal problem. |

## 4 Overall Risk

| Tier   | Combination                            |
|--------|----------------------------------------|
| Tier 1 | High in Impact and High in Fallout     |
| Tier 2 | High in Impact and Medium in Fallout   |
| Tier 3 | Medium in Impact and Medium in Fallout |
| Tier 4 | Medium in Impact and Low in Fallout    |
| Tier 5 | Low in Impact and Low in Fallout       |

## 5 Use Case Risk Matrix

## Coding

| Use case                              | Impact   | Fallout   | Tier   | Justification                                                                                                                                                                                                                                                                                                    |
|---------------------------------------|----------|-----------|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Writing code                          | High     | Mediu m   | Tier 2 | Needs access to real company code. Bugs are usually caught in review before release.                                                                                                                                                                                                                             |
| Architecture and design brainstorming | High     | Mediu m   | Tier 2 | Touches real system design and technical decisions specific to the company. Engineers evaluate and adapt suggestions before acting on them, so a flawed idea typically gets refined out during review, though it can still cost real rework once implementation is underway if a wrong assumption slips through. |
| Debugging code                        | High     | Mediu m   | Tier 2 | Needs access to real code. Wrong fixes are usually caught during testing before release.                                                                                                                                                                                                                         |
| Code review                           | High     | High      | Tier 1 | Sees real code. A missed issue here has no other check before the code is merged.                                                                                                                                                                                                                                |
| Writing and explaining SQL queries    | Mediu m  | Mediu m   | Tier 3 | Shows the shape of the database. A wrong query can quietly give a misleading result if nobody checks it.                                                                                                                                                                                                         |

## QA and Testing

| Use case                           | Impact   | Fallout   | Tier   | Justification                                                                                                   |
|------------------------------------|----------|-----------|--------|-----------------------------------------------------------------------------------------------------------------|
| Root cause analysis assistance     | Mediu m  | High      | Tier 2 | Uses internal system information. A wrong diagnosis can sound convincing and get acted on before anyone checks. |
| Troubleshooting steps              | Mediu m  | Mediu m   | Tier 3 | Uses internal system information. Wrong steps are usually noticed when the problem is still not fixed.          |
| Test case and test plan generation | Mediu m  | Mediu m   | Tier 3 | Sees feature details. Gaps in coverage may not show up until later testing.                                     |
| Generating test cases              | Mediu m  | Mediu m   | Tier 3 | Sees feature details. Missing cases can let a real problem slip through if nobody reviews it.                   |
| Bug report writing                 | Mediu m  | Low       | Tier 4 | Describes internal product behaviour. Mistakes are usually caught during triage.                                |

<!-- image -->

CLARISYNC

## Documentation

| Use case                                  | Impact   | Fallout   | Tier   | Justification                                                                                                         |
|-------------------------------------------|----------|-----------|--------|-----------------------------------------------------------------------------------------------------------------------|
| API documentation                         | High     | Mediu m   | Tier 2 | Describes real system structure. Misleading documentation is usually caught when something fails to connect properly. |
| Writing user manuals and product docs     | Mediu m  | Mediu m   | Tier 3 | Describes product details. A mistake that reaches a published manual could mislead an outside reader.                 |
| Drafting SOPs and process docs            | Mediu m  | Mediu m   | Tier 3 | Describes an internal process. An unreviewed mistake can become a permanent wrong step.                               |
| Internal wiki and knowledge base articles | Mediu m  | Mediu m   | Tier 3 | Becomes a lasting internal reference. An uncaught mistake can spread to everyone who reads it.                        |
| Slides and presentation content           | Mediu m  | Low       | Tier 4 | May include internal business information. The presenter usually checks it before sharing.                            |
| Policy drafting                           | Mediu m  | Mediu m   | Tier 3 | Internal governance content. An unclear clause can cause confusion until someone reviews it.                          |
| Job description drafting                  | Low      | Low       | Tier 5 | Fairly general content, and HR checks it before posting. Low harm even if something is off.                           |
| Onboarding docs                           | Low      | Low       | Tier 5 | General process information, checked by a manager or HR before use.                                                   |
| FAQ and help centre content               | Low      | Low       | Tier 5 | Meant to be public anyway, and checked before it goes live. Low harm even if slightly off.                            |

<!-- image -->

CLARISYNC

## Data Sorting and Analysis

| Use case                            | Impact   | Fallout   | Tier   | Justification                                                                                                     |
|-------------------------------------|----------|-----------|--------|-------------------------------------------------------------------------------------------------------------------|
| Spreadsheet and data analysis       | Mediu m  | High      | Tier 2 | Works with internal business data. A wrong number can feed directly into a decision before anyone rechecks it.    |
| Budget and expense analysis         | Mediu m  | High      | Tier 2 | Works with internal financial data. An unnoticed mistake can shape a real budget decision.                        |
| Forecasting and financial modelling | Mediu m  | High      | Tier 2 | Uses internal financial data. A flawed forecast can drive a decision before it is checked independently.          |
| Resume screening and summarising    | Mediu m  | High      | Tier 2 | Involves a candidate's personal details. A wrong summary can affect a hiring decision if nobody double checks it. |
| Summarising reports and data        | Mediu m  | Mediu m   | Tier 3 | Summarises internal reports. A wrong figure can mislead a reader who does not check the original.                 |
| Market and competitor research      | Low      | Mediu m   | Tier 4 | Uses information that is already public. A confident but wrong conclusion could still steer a decision.           |
| Ticket triage and categorisation    | Mediu m  | Low       | Tier 4 | Works with customer support content. Wrong categorising is usually noticed and fixed quickly.                     |

<!-- image -->

CLARISYNC

## Rephrasing and Drafting

| Use case                               | Impact   | Fallout   | Tier   | Justification                                                                                                    |
|----------------------------------------|----------|-----------|--------|------------------------------------------------------------------------------------------------------------------|
| Summarising long documents and threads | Mediu m  | Low       | Tier 4 | May include internal discussion. The original document is still there to check against.                          |
| Meeting notes and minutes              | Mediu m  | Low       | Tier 4 | May capture internal discussion. Attendees can catch anything wrong against what they remember.                  |
| Drafting customer and client replies   | Mediu m  | Mediu m   | Tier 3 | May mention a customer's account details. An unreviewed wrong reply can affect the relationship.                 |
| Performance review drafting            | Mediu m  | Mediu m   | Tier 3 | Involves an employee's performance information. An inaccurate draft could affect someone if it goes uncorrected. |
| Vendor communication drafting          | Mediu m  | Mediu m   | Tier 3 | May mention contract or vendor terms. An unreviewed mistake could affect the vendor relationship.                |
| Invoice and financial report drafting  | Mediu m  | Mediu m   | Tier 3 | Involves internal financial figures. Mistakes are usually caught during normal finance review.                   |
| Proofreading and editing               | Low      | Low       | Tier 5 | No real judgment involved beyond fixing a draft. Mistakes are obvious right away.                                |
| Drafting emails                        | Low      | Low       | Tier 5 | Ordinary content with no real judgment involved. The sender checks it before sending.                            |
| Translating text                       | Low      | Low       | Tier 5 | A simple transformation task. A bilingual reviewer can catch mistakes before use.                                |
| Scheduling and admin coordination      | Low      | Low       | Tier 5 | Routine admin content with no real judgment involved. Mistakes are noticed and fixed quickly.                    |

## Security and Risk Review

| Use case                   | Impact   | Fallout   | Tier   | Justification                                                                                                           |
|----------------------------|----------|-----------|--------|-------------------------------------------------------------------------------------------------------------------------|
| Code vulnerability review  | High     | High      | Tier 1 | Sees real source code. A missed vulnerability means it ships without anyone knowing.                                    |
| Analysing logs and alerts  | High     | High      | Tier 1 | Sees internal system and security logs. A missed alert can let a real security problem go unnoticed.                    |
| Threat and CVE research    | High     | High      | Tier 1 | Tied directly to the company's security posture. A missed threat can leave a real weakness unaddressed.                 |
| Contract and policy review | High     | High      | Tier 1 | Involves private contract terms. A misread clause can create legal trouble before anyone catches it.                    |
| Incident report drafting   | High     | Mediu m   | Tier 2 | Documents sensitive incident details. Security reviews it before action, but the detail itself is still very sensitive. |

<!-- image -->

CLARISYNC

## Totals: Tier 1: 5, Tier 2: 10, Tier 3: 13, Tier 4: 6, Tier 5: 7

## 6 What Tier 1 and Tier 2 Are Actually Exposing

The 15 Tier 1 and Tier 2 use cases - the two tiers where Impact hits High - are not all dangerous for the same reason. This section groups them by what they actually expose, so the pattern is visible rather than buried in 15 separate rows.

| Exposure Type         |   Count | Use Cases                                                                                                                      |
|-----------------------|---------|--------------------------------------------------------------------------------------------------------------------------------|
| IP and proprietary    |       6 | Writing code, Architecture and design brainstorming, Debugging code, Code review, API documentation, Code vulnerability review |
| Security posture      |       3 | Analysing logs and alerts, Threat and CVE research, Incident report drafting                                                   |
| Financial data        |       3 | Spreadsheet and data analysis, Budget and expense analysis, Forecasting and financial modelling                                |
| Legal and contractual |       1 | Contract and policy review                                                                                                     |
| Personal data         |       1 | Resume screening and summarising                                                                                               |
| Internal operational  |       1 | Root cause analysis assistance                                                                                                 |

6 of the 15 Tier 1 and Tier 2 use cases expose IP or proprietary information. That is the single largest group in the two highest tiers, and it matches the priority already set for this project. IP exposure is treated as more serious than financial exposure, and the numbers here show why that priority matters in practice, not just in principle.

## 7 Use Cases by Tier

Tier 1 - 5 use cases

| Use case                   | Category                 | Impact   | Fallout   |
|----------------------------|--------------------------|----------|-----------|
| Code review                | Coding                   | High     | High      |
| Code vulnerability review  | Security and Risk Review | High     | High      |
| Analysing logs and alerts  | Security and Risk Review | High     | High      |
| Threat and CVE research    | Security and Risk Review | High     | High      |
| Contract and policy review | Security and Risk Review | High     | High      |

<!-- image -->

CLARISYNC

## Tier 2 - 10 use cases

| Use case                              | Category                  | Impact   | Fallout   |
|---------------------------------------|---------------------------|----------|-----------|
| Writing code                          | Coding                    | High     | Medium    |
| Architecture and design brainstorming | Coding                    | High     | Medium    |
| Debugging code                        | Coding                    | High     | Medium    |
| Root cause analysis assistance        | QA and Testing            | Medium   | High      |
| API documentation                     | Documentation             | High     | Medium    |
| Spreadsheet and data analysis         | Data Sorting and Analysis | Medium   | High      |
| Budget and expense analysis           | Data Sorting and Analysis | Medium   | High      |
| Forecasting and financial modelling   | Data Sorting and Analysis | Medium   | High      |
| Resume screening and summarising      | Data Sorting and Analysis | Medium   | High      |
| Incident report drafting              | Security and Risk Review  | High     | Medium    |

## Tier 3 - 13 use cases

| Use case                                  | Category                  | Impact   | Fallout   |
|-------------------------------------------|---------------------------|----------|-----------|
| Writing and explaining SQL queries        | Coding                    | Medium   | Medium    |
| Troubleshooting steps                     | QA and Testing            | Medium   | Medium    |
| Test case and test plan generation        | QA and Testing            | Medium   | Medium    |
| Generating test cases                     | QA and Testing            | Medium   | Medium    |
| Writing user manuals and product docs     | Documentation             | Medium   | Medium    |
| Drafting SOPs and process docs            | Documentation             | Medium   | Medium    |
| Internal wiki and knowledge base articles | Documentation             | Medium   | Medium    |
| Policy drafting                           | Documentation             | Medium   | Medium    |
| Summarising reports and data              | Data Sorting and Analysis | Medium   | Medium    |
| Drafting customer and client replies      | Rephrasing and Drafting   | Medium   | Medium    |
| Performance review drafting               | Rephrasing and Drafting   | Medium   | Medium    |
| Vendor communication drafting             | Rephrasing and Drafting   | Medium   | Medium    |
| Invoice and financial report drafting     | Rephrasing and Drafting   | Medium   | Medium    |

<!-- image -->

CLARISYNC

## Tier 4 - 6 use cases

| Use case                               | Category                  | Impact   | Fallout   |
|----------------------------------------|---------------------------|----------|-----------|
| Bug report writing                     | QA and Testing            | Medium   | Low       |
| Slides and presentation content        | Documentation             | Medium   | Low       |
| Market and competitor research         | Data Sorting and Analysis | Low      | Medium    |
| Ticket triage and categorisation       | Data Sorting and Analysis | Medium   | Low       |
| Summarising long documents and threads | Rephrasing and Drafting   | Medium   | Low       |
| Meeting notes and minutes              | Rephrasing and Drafting   | Medium   | Low       |

## Tier 5 - 7 use cases

| Use case                          | Category                | Impact   | Fallout   |
|-----------------------------------|-------------------------|----------|-----------|
| Job description drafting          | Documentation           | Low      | Low       |
| Onboarding docs                   | Documentation           | Low      | Low       |
| FAQ and help centre content       | Documentation           | Low      | Low       |
| Proofreading and editing          | Rephrasing and Drafting | Low      | Low       |
| Drafting emails                   | Rephrasing and Drafting | Low      | Low       |
| Translating text                  | Rephrasing and Drafting | Low      | Low       |
| Scheduling and admin coordination | Rephrasing and Drafting | Low      | Low       |

## 8 Use Case Buckets

## Coding

| Use Case                              | Adoption   | Tier   | Model Category   |
|---------------------------------------|------------|--------|------------------|
| Writing code                          | 48%        | Tier 2 | Coding           |
| Architecture and design brainstorming | 42%        | Tier 2 | Coding           |
| Debugging code                        | 38%        | Tier 2 | Coding           |
| Code review                           | 35%        | Tier 1 | Coding           |
| Writing and explaining SQL queries    | 15%        | Tier 3 | Coding           |

<!-- image -->

CLARISYNC

## QA and Testing

| Use Case                           | Adoption   | Tier   | Model Category   |
|------------------------------------|------------|--------|------------------|
| Root cause analysis assistance     | 33%        | Tier 2 | Deep             |
| Troubleshooting steps              | 31%        | Tier 3 | Deep             |
| Test case and test plan generation | 29%        | Tier 3 | General          |
| Generating test cases              | 21%        | Tier 3 | Coding           |
| Bug report writing                 | 15%        | Tier 4 | Quick            |

## Documentation

| Use Case                                  | Adoption   | Tier   | Model Category   |
|-------------------------------------------|------------|--------|------------------|
| API documentation                         | 19%        | Tier 2 | Coding           |
| Writing user manuals and product docs     | 44%        | Tier 3 | General          |
| Drafting SOPs and process docs            | 42%        | Tier 3 | General          |
| Internal wiki and knowledge base articles | 35%        | Tier 3 | General          |
| Slides and presentation content           | 42%        | Tier 4 | General          |
| Policy drafting                           | 8%         | Tier 3 | General          |
| Job description drafting                  | 21%        | Tier 5 | Quick            |
| Onboarding docs                           | 6%         | Tier 5 | General          |
| FAQ and help centre content               | 4%         | Tier 5 | Quick            |

## Data Sorting and Analysis

| Use Case                            | Adoption   | Tier   | Model Category   |
|-------------------------------------|------------|--------|------------------|
| Spreadsheet and data analysis       | 38%        | Tier 2 | Deep             |
| Budget and expense analysis         | 17%        | Tier 2 | Deep             |
| Forecasting and financial modelling | 12%        | Tier 2 | Deep             |
| Resume screening and summarising    | 6%         | Tier 2 | General          |
| Summarising reports and data        | 65%        | Tier 3 | General          |
| Market and competitor research      | 40%        | Tier 4 | General          |
| Ticket triage and categorisation    | 12%        | Tier 4 | Quick            |

<!-- image -->

CLARISYNC

## Rephrasing and Drafting

| Use Case                               | Adoption   | Tier   | Model Category   |
|----------------------------------------|------------|--------|------------------|
| Summarising long documents and threads | 65%        | Tier 4 | General          |
| Meeting notes and minutes              | 23%        | Tier 4 | Quick            |
| Drafting customer and client replies   | 19%        | Tier 3 | Quick            |
| Performance review drafting            | 15%        | Tier 3 | General          |
| Vendor communication drafting          | 10%        | Tier 3 | Quick            |
| Invoice and financial report drafting  | 6%         | Tier 3 | General          |
| Proofreading and editing               | 56%        | Tier 5 | Quick            |
| Drafting emails                        | 50%        | Tier 5 | Quick            |
| Translating text                       | 15%        | Tier 5 | Quick            |
| Scheduling and admin coordination      | 2%         | Tier 5 | Quick            |

## Security and Risk Review

| Use Case                   | Adoption   | Tier   | Model Category   |
|----------------------------|------------|--------|------------------|
| Code vulnerability review  | 29%        | Tier 1 | Coding           |
| Analysing logs and alerts  | 17%        | Tier 1 | Deep             |
| Threat and CVE research    | 2%         | Tier 1 | Deep             |
| Contract and policy review | 2%         | Tier 1 | Deep             |
| Incident report drafting   | 15%        | Tier 2 | General          |

## 9 Model Recommendations

Coding: to be decided, no candidates researched yet.

## Quick Assistant

| Model       | Role      | VRAM (Q4)   | License    | Note                                                                                  |
|-------------|-----------|-------------|------------|---------------------------------------------------------------------------------------|
| Mistral 7B  | Incumbent | 4.4 GB      | Apache 2.0 | Locally tested, number 2 overall. Best summary fidelity and length discipline.        |
| Qwen3.5-9B  | Candidate | 5.5 GB      | Apache 2.0 | Strongest model under 10B parameters on general reasoning benchmarks. Not yet tested. |
| Gemma 4 12B | Candidate | 6.6 GB      | Apache 2.0 | Beats Gemma 3 27B on MMLU Pro at less than half the size.                             |

<!-- image -->

CLARISYNC

<!-- image -->

CLARISYNC

| Model          | Role      | VRAM (Q4)   | License    | Note                                                            |
|----------------|-----------|-------------|------------|-----------------------------------------------------------------|
| Ministral 3 8B | Candidate | 4.8 GB      | Apache 2.0 | Mistral's own successor to the tested 7B. Lowest risk fallback. |

## General Assistant

| Model                  | Role      | VRAM (Q4)   | License               | Note                                                                                 |
|------------------------|-----------|-------------|-----------------------|--------------------------------------------------------------------------------------|
| GPT-OSS 20B            | Incumbent | ~13 GB      | Apache style (OpenAI) | Never empirically tested. Carrying majority of daily work on spec sheet trust alone. |
| Qwen3.6-27B            | Candidate | 16.8 GB     | Apache 2.0            | Ties Sonnet 4.6 on AA Agentic Index. Untested locally.                               |
| NVIDIA Nemotron 3 Nano | Candidate | 19.0 GB     | NVIDIA open license   | Ahead of GPT-OSS 20B and Qwen3-30B-A3B on accuracy, more than 2x throughput.         |
| GLM-4.7-Flash          | Candidate | 18.0 GB     | Custom (verify terms) | Runs on consumer GPU. Similar efficiency profile to Nemotron 3 Nano.                 |

## Deep Assistant

| Model                            | Role      | VRAM (Q4)   | License             | Note                                                                                                                                                                        |
|----------------------------------|-----------|-------------|---------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| DeepSeek R1 Distill Qwen 32B     | Incumbent | 19.5 GB     | MIT                 | Best local reasoning after baseline. Needs 3 configs and a pinned seed to terminate. Rumination bug confirmed at 8B, untested at 32B.                                       |
| Qwen3-32B (thinking mode)        | Candidate | 19.7 GB     | Apache 2.0          | Trained natively through reinforcement learning. Beats DeepSeek R1 Distill Llama 70B at half the size.                                                                      |
| NVIDIA Nemotron 3 Nano Reasoning | Candidate | 18.6 GB     | NVIDIA open license | Dedicated reasoning variant, NVFP4 native.                                                                                                                                  |
| QwQ-32B                          | Candidate | 19.5 GB     | Apache 2.0          | Most proven reasoning model on the list, with more production hours behind it than other candidates. Matches DeepSeek R1 671B on math and coding at a fraction of the size. |

## Quantization

- Well calibrated Q4 (AWQ, GPTQ, Q4\_K\_M) against an FP16 baseline typically costs about 1 to 3% on general tasks, drafting, summarizing, and everyday writing.
- Complex multi step reasoning degrades more at the same bit width, roughly 3 to 5%, about double the general task hit, per one benchmark source.
- FP16 uses 2 bytes per param, matching every reported figure exactly. Q4 uses about 0.60 bytes per param, calibrated against four confirmed Q4\_K\_M sizes.

<!-- image -->

CLARISYNC

- MoE rows are sized on total params, since every expert must be VRAM resident even though only the active fraction computes per token.

| Assistant   | Model                     | Params              | FP16    | FP8     | Q4                    |
|-------------|---------------------------|---------------------|---------|---------|-----------------------|
| Quick       | Mistral 7B                | 7.3B dense          | 14.6 GB | 7.7 GB  | 4.4 GB (confirmed)    |
| Quick       | Qwen3.5-9B                | 9B dense            | 18.0 GB | 9.5 GB  | 5.5 GB (confirmed)    |
| Quick       | Gemma 4 12B               | 11.95B dense        | 23.9 GB | 12.5 GB | 6.6 GB (confirmed)    |
| Quick       | Ministral 3 8B            | 8B dense            | 16.0 GB | 8.4 GB  | 4.8 GB (est.)         |
| General     | GPT-OSS 20B               | 20.9B / 3.6B active | -       | -       | ~13 GB (ships native) |
| General     | Qwen3.6-27B               | 27.8B dense         | 55.6 GB | 29.2 GB | 16.8 GB (confirmed)   |
| General     | Nemotron 3 Nano           | 31.6B / 3.2B active | 63.2 GB | 33.2 GB | 19.0 GB (est.)        |
| General     | GLM-4.7-Flash             | 30B / 3B active     | 60.0 GB | 31.5 GB | 18.0 GB (est.)        |
| Deep        | DeepSeek R1 Distill 32B   | 32.5B dense         | 65.0 GB | 34.1 GB | 19.5 GB (est.)        |
| Deep        | Qwen3-32B                 | 32.8B dense         | 65.6 GB | 34.4 GB | 19.7 GB (confirmed)   |
| Deep        | Nemotron 3 Nano Reasoning | 31B / 3B active     | 62.0 GB | 32.6 GB | 18.6 GB (est.)        |
| Deep        | QwQ-32B                   | 32.5B dense         | 65.0 GB | 34.1 GB | 19.5 GB (est.)        |