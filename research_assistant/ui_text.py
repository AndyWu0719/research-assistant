from __future__ import annotations

from typing import Any

from research_assistant.language import normalize_language


NAV_ITEMS = [
    ("home", "app.py"),
    ("literature_scout", "pages/literature_scout.py"),
    ("paper_reader", "pages/paper_reader.py"),
    ("topic_mapper", "pages/topic_mapper.py"),
    ("idea_feasibility", "pages/idea_feasibility.py"),
    ("constraint_explorer", "pages/constraint_explorer.py"),
    ("pdf_fetcher", "pages/pdf_fetcher.py"),
    ("automation_config", "pages/automation_config.py"),
]

PAGE_COPY = {
    "home": {
        "nav_label": {"zh-CN": "首页", "en-US": "Home"},
        "title": {"zh-CN": "本地研究助手", "en-US": "Research Assistant"},
        "caption": {
            "zh-CN": "桌面应用负责参数配置、执行与结果查看，本地 Codex CLI 负责真实研究任务；周期任务默认由本地调度器承担。",
            "en-US": "The desktop app handles inputs, execution, and result review, while the local Codex CLI runs the real research tasks. Recurring runs default to the local scheduler.",
        },
    },
    "literature_scout": {
        "nav_label": {"zh-CN": "文献巡检", "en-US": "Literature Scan"},
        "title": {"zh-CN": "文献巡检", "en-US": "Literature Scan"},
        "caption": {
            "zh-CN": "按研究主题、时间范围和排序偏好做一次真实文献巡检，并把结果写回 `outputs/literature_scans/`。",
            "en-US": "Run a real literature scan for a research topic, time window, and ranking profile, then write the result to `outputs/literature_scans/`.",
        },
    },
    "paper_reader": {
        "nav_label": {"zh-CN": "单篇论文精读", "en-US": "Paper Deep Read"},
        "title": {"zh-CN": "单篇论文精读", "en-US": "Paper Deep Read"},
        "caption": {
            "zh-CN": "支持链接、arXiv ID、DOI 和本地 PDF；如可拿到 PDF，会先做本地文本抽取与清洗，再进入精读链路。",
            "en-US": "Supports URLs, arXiv IDs, DOIs, and local PDFs. When a PDF is available, the app extracts and cleans local text before deep reading.",
        },
    },
    "topic_mapper": {
        "nav_label": {"zh-CN": "方向地图", "en-US": "Topic Map"},
        "title": {"zh-CN": "研究方向地图", "en-US": "Topic Map"},
        "caption": {
            "zh-CN": "围绕一个方向做分层论文地图、主题簇和阅读路径。",
            "en-US": "Build a layered paper map, topic clusters, and reading path for a research direction.",
        },
    },
    "idea_feasibility": {
        "nav_label": {"zh-CN": "想法可行性", "en-US": "Idea Feasibility"},
        "title": {"zh-CN": "研究想法可行性", "en-US": "Idea Feasibility"},
        "caption": {
            "zh-CN": "围绕研究想法做相关工作、风险和最小可行验证路径分析。",
            "en-US": "Evaluate related work, risks, and a minimum viable validation path for a research idea.",
        },
    },
    "constraint_explorer": {
        "nav_label": {"zh-CN": "约束探索", "en-US": "Constraint Explorer"},
        "title": {"zh-CN": "资源约束探索", "en-US": "Constraint Explorer"},
        "caption": {
            "zh-CN": "先判断资源约束下的可行边界，再推荐更可做的方向与最低成本路径。",
            "en-US": "Assess the feasible boundary under resource constraints first, then recommend practical directions and low-cost paths.",
        },
    },
    "pdf_fetcher": {
        "nav_label": {"zh-CN": "PDF 下载", "en-US": "PDF Downloads"},
        "title": {"zh-CN": "PDF 下载", "en-US": "PDF Downloads"},
        "caption": {
            "zh-CN": "通过本地脚本真实下载 PDF；需要时可直接串到单篇论文精读。",
            "en-US": "Download PDFs through the local script, and optionally chain the result directly into paper deep reading.",
        },
    },
    "automation_config": {
        "nav_label": {"zh-CN": "自动化配置", "en-US": "Automation Setup"},
        "title": {"zh-CN": "自动化配置", "en-US": "Automation Setup"},
        "caption": {
            "zh-CN": "保存每日巡检配置、生成稳定的 automation 配置文件名，并管理本地调度器使用的自动化参数。",
            "en-US": "Save the daily scan settings, generate a stable automation config filename, and manage automation parameters for the local scheduler.",
        },
    },
}

EXPANDER_TITLES = {
    "advanced_options": {"zh-CN": "高级选项", "en-US": "Advanced Options"},
    "raw_prompt": {"zh-CN": "原始 Prompt", "en-US": "Raw Prompt"},
    "output_paths": {"zh-CN": "输出与文件路径", "en-US": "Output Paths"},
    "debug_details": {"zh-CN": "调试与执行详情", "en-US": "Debug Details"},
    "metadata_sidecar": {"zh-CN": "Metadata Sidecar", "en-US": "Metadata Sidecar"},
    "local_environment": {"zh-CN": "本地执行环境", "en-US": "Local Execution Environment"},
    "pdf_extraction": {"zh-CN": "PDF 抽取详情", "en-US": "PDF Extraction Details"},
    "config_preview": {"zh-CN": "配置预览", "en-US": "Config Preview"},
    "saved_preferences": {"zh-CN": "本地偏好与记忆", "en-US": "Saved Preferences"},
    "paths_and_storage": {"zh-CN": "路径与落盘信息", "en-US": "Paths And Storage"},
}

HOME_PARAMETER_GLOSSARY = {
    "zh-CN": [
        ("研究领域", "你想关注的主题，例如 long-context multimodal reasoning 或 speech representation learning。"),
        ("时间范围", "限制检索窗口。窗口越短越偏最新，窗口越长越适合做稳定综述。"),
        ("来源范围", "限定主要检索站点。普通用户建议先选 arXiv 和 OpenReview，再逐步扩展。"),
        ("排序 Profile", "决定排序优先级。`balanced-default` 偏通用，`trend-focused` 偏热点，`resource-constrained` 偏可落地。"),
        ("约束条件", "描述算力、数据、时间、预算、团队等现实边界。给得越具体，推荐越可执行。"),
        ("执行质量档位", "控制模型与推理强度。普通验证优先 economy 或 balanced；只有确实需要时再切高档位。"),
        ("下载并精读", "先真实下载 PDF，再进行本地文本抽取、质量评估和结构化精读。"),
    ],
    "en-US": [
        ("Research Area", "The topic you care about, such as long-context multimodal reasoning or speech representation learning."),
        ("Time Range", "Limits the search window. Shorter windows bias toward freshness, while longer windows are better for stable overviews."),
        ("Sources", "Restricts the main search sites. For most users, start with arXiv and OpenReview, then expand only when needed."),
        ("Ranking Profile", "Controls ranking priorities. `balanced-default` is general purpose, `trend-focused` emphasizes momentum, and `resource-constrained` emphasizes practicality."),
        ("Constraints", "Describe real limits such as compute, data, time, budget, and team size. The more specific this is, the more actionable the recommendations become."),
        ("Execution Quality", "Controls model and reasoning strength. Use economy or balanced for routine validation, and only raise the level when necessary."),
        ("Download And Read", "Downloads the PDF first, then runs local text extraction, quality checks, and structured deep reading."),
    ],
}

HOME_FEATURE_OVERVIEW = {
    "zh-CN": [
        ("文献巡检", "适合每天或每周快速收敛值得跟进的新论文。"),
        ("单篇论文精读", "适合理解一篇具体论文的方法、实验、局限和复现门槛。"),
        ("研究方向地图", "适合在进入一个新方向前先搭好阅读地图。"),
        ("研究想法可行性", "适合在动手前先判断一个想法值不值得做。"),
        ("资源约束探索", "适合在算力、数据或时间有限时找低成本切入口。"),
        ("PDF 下载", "适合把论文先落到本地，再做后续精读或归档。"),
        ("自动化配置", "适合把固定巡检任务做成重复运行的 automation。"),
    ],
    "en-US": [
        ("Literature Scan", "Best for quickly narrowing down papers worth following on a daily or weekly basis."),
        ("Paper Deep Read", "Best for understanding one specific paper, including its method, experiments, limitations, and reproduction cost."),
        ("Topic Map", "Best for building a reading map before entering a new research direction."),
        ("Idea Feasibility", "Best for checking whether an idea is worth pursuing before implementation."),
        ("Constraint Explorer", "Best for finding low-cost entry points when compute, data, or time is limited."),
        ("PDF Downloads", "Best for saving papers locally before reading or archiving them."),
        ("Automation Setup", "Best for turning a recurring scan into a reusable automation."),
    ],
}

SUMMARY_DEPTH_OPTIONS = ["standard", "deep", "very_deep"]
SUMMARY_DEPTH_ALIASES = {
    "standard": {"standard", "标准"},
    "deep": {"deep", "深入"},
    "very_deep": {"very_deep", "超详细", "very deep"},
}
SUMMARY_DEPTH_LABELS = {
    "standard": {"zh-CN": "标准", "en-US": "Standard"},
    "deep": {"zh-CN": "深入", "en-US": "Deep"},
    "very_deep": {"zh-CN": "超详细", "en-US": "Very Deep"},
}

RISK_PREFERENCE_OPTIONS = ["conservative", "balanced", "aggressive"]
RISK_PREFERENCE_ALIASES = {
    "conservative": {"conservative", "保守"},
    "balanced": {"balanced", "平衡"},
    "aggressive": {"aggressive", "激进"},
}
RISK_PREFERENCE_LABELS = {
    "conservative": {"zh-CN": "保守", "en-US": "Conservative"},
    "balanced": {"zh-CN": "平衡", "en-US": "Balanced"},
    "aggressive": {"zh-CN": "激进", "en-US": "Aggressive"},
}

SECTION_GROUPS = {
    "overview": {
        "label": {"zh-CN": "概览", "en-US": "Overview"},
        "aliases": {"overview", "概览"},
    },
    "one_sentence": {
        "label": {"zh-CN": "一句话总结", "en-US": "One-Sentence Summary"},
        "aliases": {"一句话总结", "one-sentence summary", "one sentence summary"},
    },
    "paper_overview": {
        "label": {"zh-CN": "论文速览", "en-US": "Paper Overview"},
        "aliases": {"论文速览", "paper overview"},
    },
    "background": {
        "label": {"zh-CN": "研究背景", "en-US": "Background"},
        "aliases": {"研究背景", "background"},
    },
    "goal": {
        "label": {"zh-CN": "目标", "en-US": "Goal"},
        "aliases": {"目标", "goal"},
    },
    "core_problem_and_method": {
        "label": {"zh-CN": "核心问题与方法", "en-US": "Core Problem And Method"},
        "aliases": {"核心问题与方法", "core problem and method"},
    },
    "core_method": {
        "label": {"zh-CN": "核心方法", "en-US": "Core Method"},
        "aliases": {"核心方法", "core method", "method"},
    },
    "key_experiments_and_conclusions": {
        "label": {"zh-CN": "关键实验与结论", "en-US": "Key Experiments And Conclusions"},
        "aliases": {"关键实验与结论", "key experiments and conclusions"},
    },
    "experiments": {
        "label": {"zh-CN": "实验细节", "en-US": "Experimental Details"},
        "aliases": {"实验细节", "experimental details", "experiments"},
    },
    "results": {
        "label": {"zh-CN": "结果", "en-US": "Results"},
        "aliases": {"结果", "results"},
    },
    "limitations": {
        "label": {"zh-CN": "局限性", "en-US": "Limitations"},
        "aliases": {"局限性", "limitations"},
    },
    "open_resources": {
        "label": {"zh-CN": "开源资源", "en-US": "Open Resources"},
        "aliases": {"开源资源", "open resources"},
    },
    "diagram_plain": {
        "label": {"zh-CN": "通俗图示", "en-US": "Plain-Language Diagram"},
        "aliases": {"通俗图示", "plain-language diagram"},
    },
    "diagram_explanation": {
        "label": {"zh-CN": "图示化解释", "en-US": "Diagram Explanation"},
        "aliases": {"图示化解释", "diagram explanation"},
    },
    "task_definition": {
        "label": {"zh-CN": "任务定义", "en-US": "Task Definition"},
        "aliases": {"任务定义", "task definition"},
    },
}

TEXT = {
    "zh-CN": {
        "sidebar": {
            "title": "Research Assistant",
            "navigation": "导航",
            "language": "界面语言",
            "preference_language": "语言偏好",
            "preference_path": "偏好配置",
            "current_automation_config": "当前自动化配置",
        },
        "common": {
            "field": "研究领域",
            "time_range": "时间范围",
            "time_window": "时间窗口",
            "sources": "来源范围",
            "ranking_profile": "排序 Profile",
            "quality_profile": "执行质量档位",
            "top_k": "Top K",
            "constraints": "约束条件",
            "result_file": "结果文件路径",
            "json_sidecar": "JSON Sidecar",
            "markdown": "Markdown",
            "status_heading": "本次执行状态",
            "history_loaded": "已回读历史结果。",
            "select_result_file": "选择结果文件",
            "output_and_paths": "输出与文件路径",
            "execution_summary": "执行摘要",
            "current_result": "本次结果回读",
            "current_read_result": "本次精读结果",
            "recent_results": "最近结果",
            "download_status": "下载状态",
            "read_status": "精读状态",
            "read_preview": "精读结果预览",
            "task": "任务",
            "quality_profile_line": "质量档位",
            "model": "模型",
            "reasoning_effort": "reasoning effort",
            "control_level": "控制状态",
            "execution_mode": "执行模式",
            "failure_reason": "失败原因",
            "version": "版本",
            "executable_path": "可执行路径",
            "login_mode": "登录方式",
            "issue": "问题",
            "note": "说明",
            "yes": "是",
            "no": "否",
            "enabled": "启用",
            "disabled": "停用",
            "not_provided": "未提供",
            "not_recorded": "未记录",
            "not_found": "未找到",
            "unknown": "未知",
            "none_yet": "还没有结果。",
            "language_display": "默认输出语言",
            "recommended_model": "推荐模型",
            "recommended_reasoning": "推荐 reasoning effort",
            "interesting_status": "感兴趣状态",
            "marked": "已标记",
            "unmarked": "未标记",
            "paper_link": "论文链接",
            "code_link": "代码链接",
            "why_relevant": "相关性原因",
            "why_priority": "排名原因",
            "priority": "推荐优先级",
            "candidate_links": "候选链接：",
        },
        "home": {
            "project_heading": "项目是什么",
            "project_points": [
                "这是一个本地研究工作台：桌面应用负责表单、状态和结果回读，本地 `Codex CLI` 负责真实执行研究任务。",
                "`paper-fetcher` 继续使用本地脚本真实下载 PDF；`下载并精读` 会在进入 `paper-reader` 之前先做 PDF 文本抽取与清洗。",
                "`Automation Setup` 页面会生成可追踪的本地配置文件；本地调度器可直接执行每日任务，并默认按历史输出做去重。",
            ],
            "feature_heading": "功能概览",
            "recommended_paths_heading": "推荐使用路径",
            "beginner_path": "新手路径",
            "advanced_path": "高级用户路径",
            "defaults_heading": "默认配置",
            "parameters_heading": "参数解释与使用说明",
            "parameter_field": "字段",
            "parameter_description": "说明",
            "automation_pdf_heading": "自动化与 PDF 精读说明",
            "automation_pdf_points": [
                "`下载并精读`：先真实下载 PDF，再生成清洗文本和抽取质量 sidecar，最后才进入 `paper-reader`。",
                "`Automation Setup`：保存当前每日巡检任务配置，并显示本地调度器与手动触发命令。",
                "低成本验证建议：先用 `economy` 跑 smoke 或轻量探索；只有某条链路在低档位无法完成基本验证时，再升到 `balanced`。",
            ],
            "environment_heading": "本地执行环境",
            "capability_heading": "能力状态",
            "recent_outputs_heading": "最近产物",
            "scan_card": "文献巡检",
            "summary_card": "论文精读",
            "map_card": "方向地图",
            "feasibility_card": "可行性报告",
            "no_scan": "还没有文献巡检结果。",
            "no_summary": "还没有精读结果。",
            "no_map": "还没有方向地图结果。",
            "no_feasibility": "还没有可行性报告。",
            "paths_heading": "路径与本地记忆",
        },
        "literature_scout": {
            "quality_help": "普通巡检建议先用 balanced；只做 smoke 或非常轻量的试跑时可用 economy。",
            "constraints_placeholder": "例如：单卡 24G、优先公开代码、两周内能启动。",
            "save_as_daily": "同步保存为默认巡检配置",
            "submit": "执行巡检",
            "daily_saved": "已更新 `configs/scan_defaults.yaml`。",
            "recent_results_heading": "最近结果",
            "no_results": "还没有 `outputs/literature_scans/` 结果文件。",
            "top_k_list": "Top K 列表",
            "mark_interesting": "标记感兴趣",
            "interesting_saved": "已写入 `configs/interesting_papers.json`。",
            "already_interesting": "该论文已经在感兴趣列表中。",
            "download_pdf": "下载 PDF",
            "download_and_read": "下载并精读",
            "interest_suffix": "已标记感兴趣",
            "not_parsed": "未解析到",
            "read_preview": "精读结果预览",
        },
        "paper_reader": {
            "paper_reference": "论文链接 / arXiv ID / DOI / 本地 PDF 路径",
            "paper_reference_placeholder": "例如：1706.03762 或 /absolute/path/to/paper.pdf",
            "summary_depth": "摘要深度",
            "quality_help": "普通精读建议先用 balanced；只有明确需要更深分析时再切高档位。",
            "diagram_summary": "需要图示化解释",
            "focus_experiments": "优先解释实验细节",
            "auto_fetch_pdf": "若输入不是本地 PDF，则先自动抓 PDF",
            "submit": "执行精读",
            "pdf_fetch_chain": "PDF 获取链路",
            "recent_results_heading": "最近精读结果",
            "no_results": "还没有 `outputs/paper_summaries/` 结果。",
            "select_result_file": "选择精读结果文件",
        },
        "pdf_fetcher": {
            "references": "论文链接 / arXiv ID / DOI / OpenReview 链接",
            "references_placeholder": "每行一条，例如：\n1706.03762\nhttps://openreview.net/forum?id=YeagC09j2K",
            "auto_read": "下载后自动精读",
            "save_dir": "保存目录",
            "reader_quality_profile": "自动精读质量档位",
            "show_candidates": "下载失败时返回候选页面",
            "submit": "开始执行",
            "no_reference": "请至少输入一条论文引用。",
            "task_heading": "任务 {index}",
            "candidate_pages": "候选页面 / 候选链接：",
            "interesting_heading": "感兴趣论文列表",
            "no_interesting": "`configs/interesting_papers.json` 里还没有已标记论文。",
            "source_result": "来源结果",
            "saved_at": "标记时间",
            "download_only": "仅下载",
            "download_and_read": "下载并精读",
            "remove_mark": "移除标记",
            "removed": "已从感兴趣列表移除。",
            "not_found": "未找到对应记录。",
            "recent_read_results": "最近精读结果",
            "no_reader_results": "还没有 `paper-reader` 结果。",
        },
        "topic_mapper": {
            "topic": "方向描述",
            "topic_placeholder": "例如：长视频叙事推理中的 evidence retrieval",
            "quality_help": "这类页面现在默认先用 balanced；真实需要更深时再切高档位。",
            "cross_domain": "跨领域扩展",
            "return_count": "返回数量",
            "ranking_mode": "排序方式",
            "submit": "执行论文地图",
            "recent_results_heading": "最近方向地图",
            "no_results": "还没有 `outputs/topic_maps/` 结果。",
        },
        "idea_feasibility": {
            "idea": "研究想法",
            "target_field": "目标领域",
            "target_field_placeholder": "例如：视觉语言评测、语音表征学习",
            "compute_budget": "算力预算",
            "data_budget": "数据预算",
            "risk_preference": "风险偏好",
            "prefer_low_cost_validation": "优先低成本验证",
            "submit": "执行可行性分析",
            "recent_results_heading": "最近可行性报告",
            "no_results": "还没有 `outputs/feasibility_reports/` 结果。",
        },
        "constraint_explorer": {
            "field_placeholder": "例如：多模态长上下文、低资源语音建模",
            "compute_limit": "算力限制",
            "data_limit": "数据限制",
            "prefer_reproduction": "优先复现",
            "prefer_open_source": "优先开源",
            "submit": "执行资源受限探索",
            "recent_results_heading": "最近资源受限报告",
            "no_results": "还没有 `outputs/constraint_reports/` 结果。",
        },
        "automation_config": {
            "task_name": "任务名称",
            "run_time": "每天运行时间",
            "auto_download_interesting": "是否自动下载“已标记感兴趣”的论文",
            "enabled": "是否启用",
            "language": "默认输出语言",
            "quality_help": "每日自动化优先 balanced；只做轻量巡检时可用 economy，不建议默认 max-analysis。",
            "preview_task_name": "任务名称",
            "preview_filename": "将保存为",
            "preview_directory": "保存目录",
            "submit": "保存自动化配置",
            "saved": "配置已写入。",
            "summary_heading": "当前配置摘要",
            "quality_heading": "质量档位建议",
            "important_note": "重要说明：这里的档位会写入本地自动化配置，并用于 `codex exec` 的推荐模型与推理强度。",
            "automation_prompt": "Automation Prompt",
            "daily_profile_preview": "`configs/scan_defaults.yaml`",
            "config_preview_heading": "配置预览",
            "daily_scan_recommendation": "每日巡检建议",
            "paper_reader_recommendation": "论文精读建议",
            "deep_reports_recommendation": "深度分析建议",
            "automation_recommendation": "自动化建议",
        },
    },
    "en-US": {
        "sidebar": {
            "title": "Research Assistant",
            "navigation": "Navigation",
            "language": "Language",
            "preference_language": "Language Preference",
            "preference_path": "Preferences File",
            "current_automation_config": "Current Automation Config",
        },
        "common": {
            "field": "Research Area",
            "time_range": "Time Range",
            "time_window": "Time Window",
            "sources": "Sources",
            "ranking_profile": "Ranking Profile",
            "quality_profile": "Execution Quality",
            "top_k": "Top K",
            "constraints": "Constraints",
            "result_file": "Result File",
            "json_sidecar": "JSON Sidecar",
            "markdown": "Markdown",
            "status_heading": "Current Execution Status",
            "history_loaded": "Loaded a previous result.",
            "select_result_file": "Select A Result File",
            "output_and_paths": "Output Paths",
            "execution_summary": "Execution Summary",
            "current_result": "Current Result Preview",
            "current_read_result": "Current Reading Result",
            "recent_results": "Recent Results",
            "download_status": "Download Status",
            "read_status": "Read Status",
            "read_preview": "Reading Preview",
            "task": "Task",
            "quality_profile_line": "Quality Profile",
            "model": "Model",
            "reasoning_effort": "Reasoning Effort",
            "control_level": "Control Level",
            "execution_mode": "Execution Mode",
            "failure_reason": "Failure Reason",
            "version": "Version",
            "executable_path": "Executable Path",
            "login_mode": "Login Mode",
            "issue": "Issue",
            "note": "Note",
            "yes": "Yes",
            "no": "No",
            "enabled": "Enabled",
            "disabled": "Disabled",
            "not_provided": "Not provided",
            "not_recorded": "Not recorded",
            "not_found": "Not found",
            "unknown": "Unknown",
            "none_yet": "No results yet.",
            "language_display": "Default Output Language",
            "recommended_model": "Recommended Model",
            "recommended_reasoning": "Recommended Reasoning Effort",
            "interesting_status": "Interest Status",
            "marked": "Marked",
            "unmarked": "Not marked",
            "paper_link": "Paper Link",
            "code_link": "Code Link",
            "why_relevant": "Why Relevant",
            "why_priority": "Why Prioritized",
            "priority": "Priority",
            "candidate_links": "Candidate Links:",
        },
        "home": {
            "project_heading": "What This Project Is",
            "project_points": [
                "This is a local research workstation: the desktop app handles forms, status, and result review, while the local `Codex CLI` performs the real execution.",
                "`paper-fetcher` still downloads PDFs through the local script. `Download And Read` runs PDF text extraction and cleanup before entering `paper-reader`.",
                "The `Automation Setup` page writes trackable local config files. The local scheduler can execute recurring runs directly and deduplicate against previous daily outputs.",
            ],
            "feature_heading": "Feature Overview",
            "recommended_paths_heading": "Recommended Paths",
            "beginner_path": "Beginner Path",
            "advanced_path": "Advanced User Path",
            "defaults_heading": "Default Configuration",
            "parameters_heading": "Parameter Guide",
            "parameter_field": "Field",
            "parameter_description": "Description",
            "automation_pdf_heading": "Automation And PDF Deep Read Notes",
            "automation_pdf_points": [
                "`Download And Read`: first downloads the PDF, then writes cleaned text and an extraction-quality sidecar, and only then enters `paper-reader`.",
                "`Automation Setup`: saves the current daily scan task, and shows local scheduler commands for recurring runs.",
                "For low-cost validation, start with `economy` for smoke tests or light exploration. Only move up to `balanced` when the lower level cannot complete basic verification.",
            ],
            "environment_heading": "Local Execution Environment",
            "capability_heading": "Capability Status",
            "recent_outputs_heading": "Recent Outputs",
            "scan_card": "Literature Scans",
            "summary_card": "Paper Reads",
            "map_card": "Topic Maps",
            "feasibility_card": "Feasibility Reports",
            "no_scan": "No literature scan results yet.",
            "no_summary": "No paper reading results yet.",
            "no_map": "No topic map results yet.",
            "no_feasibility": "No feasibility reports yet.",
            "paths_heading": "Paths And Local Memory",
        },
        "literature_scout": {
            "quality_help": "For routine scans, start with balanced. Use economy for smoke tests or very lightweight trial runs.",
            "constraints_placeholder": "For example: single 24 GB GPU, prefer open code, and something the team can start within two weeks.",
            "save_as_daily": "Also Save As Scan Defaults",
            "submit": "Run Scan",
            "daily_saved": "Updated `configs/scan_defaults.yaml`.",
            "recent_results_heading": "Recent Results",
            "no_results": "No files found in `outputs/literature_scans/` yet.",
            "top_k_list": "Top K Results",
            "mark_interesting": "Mark Interesting",
            "interesting_saved": "Saved to `configs/interesting_papers.json`.",
            "already_interesting": "This paper is already in the interesting list.",
            "download_pdf": "Download PDF",
            "download_and_read": "Download And Read",
            "interest_suffix": "Marked Interesting",
            "not_parsed": "Not parsed",
            "read_preview": "Reading Preview",
        },
        "paper_reader": {
            "paper_reference": "Paper URL / arXiv ID / DOI / Local PDF Path",
            "paper_reference_placeholder": "For example: 1706.03762 or /absolute/path/to/paper.pdf",
            "summary_depth": "Summary Depth",
            "quality_help": "For routine deep reads, start with balanced. Raise the level only when deeper analysis is clearly necessary.",
            "diagram_summary": "Include Diagram-Style Explanation",
            "focus_experiments": "Prioritize Experimental Details",
            "auto_fetch_pdf": "If the input is not a local PDF, fetch the PDF first",
            "submit": "Run Deep Read",
            "pdf_fetch_chain": "PDF Fetch Pipeline",
            "recent_results_heading": "Recent Deep Reads",
            "no_results": "No files found in `outputs/paper_summaries/` yet.",
            "select_result_file": "Select A Reading Result",
        },
        "pdf_fetcher": {
            "references": "Paper URL / arXiv ID / DOI / OpenReview URL",
            "references_placeholder": "One reference per line, for example:\n1706.03762\nhttps://openreview.net/forum?id=YeagC09j2K",
            "auto_read": "Automatically Read After Download",
            "save_dir": "Save Directory",
            "reader_quality_profile": "Reader Quality Profile",
            "show_candidates": "Show Candidate Pages On Download Failure",
            "submit": "Run Download",
            "no_reference": "Enter at least one paper reference.",
            "task_heading": "Task {index}",
            "candidate_pages": "Candidate Pages / Links:",
            "interesting_heading": "Interesting Papers",
            "no_interesting": "No marked papers yet in `configs/interesting_papers.json`.",
            "source_result": "Source Result",
            "saved_at": "Saved At",
            "download_only": "Download Only",
            "download_and_read": "Download And Read",
            "remove_mark": "Remove Mark",
            "removed": "Removed from the interesting list.",
            "not_found": "No matching record was found.",
            "recent_read_results": "Recent Deep Reads",
            "no_reader_results": "No `paper-reader` results yet.",
        },
        "topic_mapper": {
            "topic": "Topic Description",
            "topic_placeholder": "For example: evidence retrieval for long-video narrative reasoning",
            "quality_help": "These pages now default to balanced. Raise the level only when deeper analysis is genuinely required.",
            "cross_domain": "Expand Across Neighboring Domains",
            "return_count": "Number Of Results",
            "ranking_mode": "Ranking Mode",
            "submit": "Run Topic Map",
            "recent_results_heading": "Recent Topic Maps",
            "no_results": "No files found in `outputs/topic_maps/` yet.",
        },
        "idea_feasibility": {
            "idea": "Research Idea",
            "target_field": "Target Field",
            "target_field_placeholder": "For example: vision-language evaluation or speech representation learning",
            "compute_budget": "Compute Budget",
            "data_budget": "Data Budget",
            "risk_preference": "Risk Preference",
            "prefer_low_cost_validation": "Prefer Low-Cost Validation",
            "submit": "Run Feasibility Analysis",
            "recent_results_heading": "Recent Feasibility Reports",
            "no_results": "No files found in `outputs/feasibility_reports/` yet.",
        },
        "constraint_explorer": {
            "field_placeholder": "For example: multimodal long context or low-resource speech modeling",
            "compute_limit": "Compute Limit",
            "data_limit": "Data Limit",
            "prefer_reproduction": "Prefer Reproducible Work",
            "prefer_open_source": "Prefer Open Source",
            "submit": "Run Constraint Explorer",
            "recent_results_heading": "Recent Constraint Reports",
            "no_results": "No files found in `outputs/constraint_reports/` yet.",
        },
        "automation_config": {
            "task_name": "Task Name",
            "run_time": "Daily Run Time",
            "auto_download_interesting": 'Automatically Download "Interesting" Papers',
            "enabled": "Enabled",
            "language": "Default Output Language",
            "quality_help": "Balanced is the default for recurring automations. Economy is fine for lighter scans, and max-analysis should not be the default.",
            "preview_task_name": "Task Name",
            "preview_filename": "Will Be Saved As",
            "preview_directory": "Save Directory",
            "submit": "Save Automation Config",
            "saved": "Configuration written successfully.",
            "summary_heading": "Current Configuration Summary",
            "quality_heading": "Quality Recommendations",
            "important_note": "Important: the quality profile is written into the local automation config and used as the recommended model and reasoning settings for `codex exec`.",
            "automation_prompt": "Automation Prompt",
            "daily_profile_preview": "`configs/scan_defaults.yaml`",
            "config_preview_heading": "Config Preview",
            "daily_scan_recommendation": "Daily Scan",
            "paper_reader_recommendation": "Paper Reader",
            "deep_reports_recommendation": "Deep Reports",
            "automation_recommendation": "Automation",
        },
    },
}


def is_english(language: str | None) -> bool:
    return normalize_language(language) == "en-US"


def _resolve_language(language: str | None) -> str:
    return normalize_language(language)


def _lookup(tree: dict[str, Any], key: str) -> Any:
    value: Any = tree
    for part in key.split("."):
        value = value[part]
    return value


def t(key: str, language: str | None = None, **kwargs: Any) -> Any:
    value = _lookup(TEXT[_resolve_language(language)], key)
    if isinstance(value, str):
        return value.format(**kwargs)
    return value


def page_copy(page_key: str, language: str | None = None) -> dict[str, str]:
    lang = _resolve_language(language)
    payload = PAGE_COPY[page_key]
    return {key: value[lang] for key, value in payload.items()}


def expander_title(key: str, language: str | None = None) -> str:
    return EXPANDER_TITLES[key][_resolve_language(language)]


def home_parameter_glossary(language: str | None = None) -> list[tuple[str, str]]:
    return list(HOME_PARAMETER_GLOSSARY[_resolve_language(language)])


def home_feature_overview(language: str | None = None) -> list[tuple[str, str]]:
    return list(HOME_FEATURE_OVERVIEW[_resolve_language(language)])


def bool_label(value: bool, language: str | None = None) -> str:
    return t("common.yes", language) if value else t("common.no", language)


def time_range_label(value: dict[str, Any] | str, language: str | None = None) -> str:
    lang = _resolve_language(language)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "7d":
            return time_range_label({"days": 7}, lang)
        if lowered == "14d":
            return time_range_label({"days": 14}, lang)
        if lowered == "30d":
            return time_range_label({"days": 30}, lang)
        if lowered == "90d":
            return time_range_label({"days": 90}, lang)
        if lowered == "1y":
            return time_range_label({"days": 365}, lang)
        return value

    days = value.get("days")
    if days == 365:
        return "Last 1 Year" if lang == "en-US" else "最近 1 年"
    if days:
        return f"Last {days} Days" if lang == "en-US" else f"最近 {days} 天"
    label = str(value.get("label") or "").strip()
    if label:
        return label
    return "Custom" if lang == "en-US" else "自定义"


def language_option_label(value: str, language: str | None = None) -> str:
    lang = _resolve_language(language)
    if value == "en-US":
        return "English" if lang == "en-US" else "English"
    return "Chinese" if lang == "en-US" else "中文"


def normalize_summary_depth(value: str | None) -> str:
    lowered = str(value or "").strip().lower()
    for key, aliases in SUMMARY_DEPTH_ALIASES.items():
        if lowered in {item.lower() for item in aliases}:
            return key
    return "standard"


def summary_depth_label(value: str | None, language: str | None = None) -> str:
    return SUMMARY_DEPTH_LABELS[normalize_summary_depth(value)][_resolve_language(language)]


def normalize_risk_preference(value: str | None) -> str:
    lowered = str(value or "").strip().lower()
    for key, aliases in RISK_PREFERENCE_ALIASES.items():
        if lowered in {item.lower() for item in aliases}:
            return key
    return "balanced"


def risk_preference_label(value: str | None, language: str | None = None) -> str:
    return RISK_PREFERENCE_LABELS[normalize_risk_preference(value)][_resolve_language(language)]


def section_key_from_title(title: str) -> str | None:
    lowered = title.strip().lower()
    if lowered == "__overview__":
        return "overview"
    for key, payload in SECTION_GROUPS.items():
        aliases = {item.lower() for item in payload["aliases"]}
        if lowered in aliases:
            return key
    return None


def section_label(key: str, language: str | None = None) -> str:
    return SECTION_GROUPS[key]["label"][_resolve_language(language)]


def section_aliases(key: str) -> set[str]:
    return {item.lower() for item in SECTION_GROUPS[key]["aliases"]}
