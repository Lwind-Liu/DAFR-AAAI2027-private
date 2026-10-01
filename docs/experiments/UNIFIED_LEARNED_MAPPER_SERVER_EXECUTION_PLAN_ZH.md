# 统一可学习工具调用—约束映射器：服务器完整执行方案

日期：2026-10-01。此文档为独立交接文件，不要求执行者读取此前聊天。

## 0. 给服务器上全新 GPT 窗口的任务

请实施本文件定义的研究与工程任务：训练一个统一的可学习映射器，在每次 Agent 提议工具调用、实际执行之前，将调用及可见多轮上下文映射为高维动作点，将任务和政策映射为同一空间中的动态可行域，并通过几何成员关系进行执行检查。

用户已表示有充足 API 与 GPU，要求最终效果可靠，而不是交付一个只演示概念的原型。你负责寻找和接入 benchmark、采集数据、生成与核验监督、实现算法、训练、评估和交付。阶段性检查属于最终方法的训练与质量控制过程，不意味着以低质量版本替代最终目标。

先检查服务器资源、已有凭据配置和仓库；可读检查、文档、工程实现和离线测试立即开展。资源信息缺失时只询问缺失项，并继续不依赖该信息的工作。未明确数值预算时不要启动无限制付费采集或长时间占满共享 GPU，先完成吞吐与费用估算，并请求本轮采集/训练的具体额度。不得在聊天、日志、配置仓库中输出密钥。

仓库：<https://github.com/Lwind-Liu/DAFR-AAAI2027-private>，起始分支 `jianghao`。编写本方案时基线提交为 `35eaaffb241dc34f7a477c92da6433c8b25ab256`。服务器如已有新提交，记录实际基线及差异，保留已有工作，不强行回退。读取适用的 AGENTS.md 和仓库贡献规范。新实现与历史 runtime 隔离。不要未经用户要求推送、覆盖共享分支或改写论文主结果。

## 1. 目标、范围与不可混淆的主张

### 1.1 最终目标

1. 一个 mapper 对所有工具采用同一接口；不区分工具接入模式和每轮调用模式。
2. 新工具通过 schema、描述和上下文理解，不逐工具手写字段映射、规则和阈值。
3. 信息选择、关系构建、表示容量分配、动作编码及语义边界由模型学习。
4. 保留决定执行合法性的细粒度区别，目标是执行相关语义近乎无损，而非逐字无损压缩任意长文本。
5. 将单次调用表示为高维点；将适用约束表示为边界/区域；状态变化更新当前点及区域。
6. 最终决定实际来自几何检查；不得先预测允许/阻断，再构造一个解释该标签的区域。
7. 在冻结模型的未见工具、领域及环境上报告迁移效果，同时保持正常任务效用。

### 1.2 范围

面向有工具规格、任务/政策和带来源多轮历史的文本/API Agent。视觉/桌面 Agent 是另一个输入模态扩展，不在主实验中假装已覆盖。任意代码执行必须拦截实际 API/工具效果；只检查代码字符串不能被写成逐效果保护。

每次检查目标是：当前效果满足已表达的政策、有效授权和前置条件，并支持用户目标或必要前置步骤。不是证明未知未来中的任务必然完成。

不可承诺未披露副作用、缺失政策或任意分布外工具都能被正确理解。未知必须显式表达，不可默认为允许，也不可把全部拒绝算成成功。

### 1.3 可固定与可学习

固定：输入来源标签的真实性、调用原值、执行结果、几何算子定义、数值稳定措施、审计协议。

学习：哪些信息保留、关系如何组合、需要多少表示槽位、约束抽取、动作坐标、几何参数和不确定性。

不能把旧七角色枚举、关键词表、45 维特征或每工具人工配置作为新 mapper 的核心。可将它们保留为历史/规则基线。原始日志可存储，但其存在不等于几何表示已保留所有关键语义。

## 2. 仓库现状与复用边界

优先检查：

- `src/clafr/policy_mapper.py`、`policy_ir.py`、`mapper_evaluation.py`：历史 LLM mapper、结构验证与评估。
- `src/clafr/features.py`、`compiler.py`、`geometry.py`、`selector.py`：历史确定性表示和执行路径。
- `docs/CODE_GUIDE.md`、`docs/COLLABORATION_WORKFLOW.md`。
- `docs/experiments/NAACL_mapper_v14_frozen_eval_ZH.md`。
- `docs/experiments/NAACL_renamed_schema_runtime_benchmark_v1_ZH.md`。
- `results/manifests/agentdojo_v122_multimodel_canonical_v1.json`。

历史 mapper prompt 含字段/词汇启发式。新方法不得把它复制后改名为可学习通用算法。历史 gold role map 实验不能作为自动映射准确率。保存 margin 的一致性审计不能作为重新执行轨迹。

历史 AgentDojo canonical 协议为四套件 71 clean / 585 attacked，历史三套件 57/389 不能混用；这些结果属于旧方法，不能继承为新模型成绩。

建议新增 `src/dafr_mapper/` 和独立配置/数据/训练目录。复用工具拦截器、日志和沙箱接口时记录版本，不替换既有 benchmark results。新依赖使用独立虚拟环境或容器，保留旧测试可运行。

## 3. 统一每轮接口与执行闭环

### 3.1 输入

`MapperInput`：

- `request_id, episode_id, step_id`。
- `candidate_call`：准确工具名称、原始参数、输入类型。
- `tool_registry`：当前可见工具规格、字段描述、返回结构、规格版本与来源。不得伪造已知 effect class。
- `trusted_task`：用户请求、可信澄清与授权事件。
- `policies`：环境业务政策及权限来源，不可从攻击文本补出授权。
- `history`：按时序保存调用、返回、异常、执行状态、来源和可见状态变化。
- `visible_state`：运行时实际提供的事实、版本、资源账本；不能包含评估器隐藏状态。

不得手工预筛掉“看似无关”的政策条款后宣称 mapper 学会了选择。大上下文通过可学习检索/记忆控制，并对检索遗漏单独测量。

### 3.2 输出

`MapperOutput`：

- `action_point z_t ∈ R^d`，必要时附动作点候选/不确定集。
- `constraints`：可变数量、具语义依据的边界和分支结构。
- `uncertainty`：约束覆盖、效果解释、证据关联等不确定项，不仅一个总 confidence。
- `evidence_links`：约束和辅助关系对应原文、字段、事件及版本。
- `representation_usage`：槽位数、保留 token/事件数、检索覆盖等审计信息。

独立 `GeometryChecker` 输出 `ALLOW / NEED_EVIDENCE / BLOCK`、每条约束 margin、限制条件、缺失依据及版本指纹。mapper 可生成辅助语义诊断，但放行位由 checker 计算。

### 3.3 运行过程

1. 从 runtime 获取完整可见输入和候选调用。
2. mapper 学习选择上下文、构建表示、生成点和区域。
3. 检查输出结构、来源链接、几何参数有效性；输出异常转为显式映射失败。
4. checker 检查成员关系与不确定性。
5. `ALLOW` 时核对候选参数及所依赖的当前版本，执行原调用。
6. 其他结果反馈给 planner，planner 提出下一步；未经授权不修改目标效果。
7. 执行后记录真实结果，更新状态/账本；失败或未执行调用不计为已完成前置条件。
8. 下一轮用同一接口重新映射。缓存只是一项经过一致性验证的优化。

NEED_EVIDENCE 与 BLOCK 的区别需要语义监督；负 margin 本身不能判断“可补充”还是“已禁止”。是否缺乏证据也不能仅用离边界近来判断。

## 4. 模型与真正的几何瓶颈

### 4.1 共享骨干、分离读出

令 `C_t=(trusted_task, policies, tool_registry, history, visible_state)`。

使用同一开放权重语言模型骨干和统一训练框架，读出：

`z_t = E_theta(C_t, candidate_call)`。

`F_t = G_theta(C_t)`。

约束路径必须在不读取候选调用的独立 forward 中生成政策/状态约束；不能仅在同一次双向 attention 中遮掉最后的输出 token。可以共享 C_t 编码缓存，不能让候选内容泄漏到区域参数。

固定 C_t 下，多个候选共用 F_t。工具特定条件通过区域中的条件分支/适用条件表达，不能见到某个候选后删除难满足的政策。完整注册表过大时，约束路径的检索必须与候选独立，或将候选条件化机制明确作为另一模型并检验政策不变性，不能偷换接口。

共享骨干并不要求两个输出互相决定。实现数据流测试：替换 candidate_call 后 F_t 的数值与结构不变（确定性 inference 下）。

### 4.2 学习信息保留

对 C_t 进行带来源/时间编码的 token/event 表示，使用可学习查询槽位和跨事件交互。槽位激活门学习容量分配，需提供 dense 与稀疏实现的梯度和推理一致性测试。

内部允许可变槽位，最后读出固定 d 的动作点；建议主实验先选 d=512，开发集比较 128/256/512/1024。维数是超参数，不是效果证据。保留更大容量的 teacher 或非压缩对照以测压缩带来的性能差距。

不手工规定 object/destination 等专属维数。可以使用自然语言关系辅助监督，但它不是闭合七角色词表。精确字段的字符/数值编码、token 级引用可保留，哪些字段需要精确读出由任务监督学习。单独测试实体标识、金额和时间扰动，防止相近 embedding 混淆不同值。

### 4.3 约束表示

约束抽取器输出可变集合，含来源依据、条件分支、满足/违反/未知语义、状态依赖。不得把每个训练样本的最终标签直接写进约束。

几何头生成：

- 半空间：`w_j^T z <= b_j`，对 w 归一化，限制数值尺度。
- 二阶锥：`||L_j z + v_j||_2 <= beta_j`；L 可低秩以控制参数量，beta 用非负参数化。
- 合取：区域交集。
- 析取：区域并集。
- 条件：保留显式分支，不能将两个合法模式平均成一个凸区。

区域可写为 `F_t = union_k intersection_j F_{t,k,j}`。所有强制政策需出现在每个相关分支；输出空约束不代表没有限制，而是覆盖检查失败。

不同几何类型不是要求 mapper 必须使用的手写语义标签。可学习选择类型，但必须有容量正则及 matched ablation，防止只是复杂 classifier。

如果 G_theta 难以一次生成庞大 DNF，可实现结构化逻辑 DAG，各叶是几何原子，按逻辑结构计算成员关系。不要把自动转换后指数膨胀的 DNF 当作必需算法。

### 4.4 margin 与放行

半空间 margin：`m_j = b_j - w_j^T z`。

锥 margin：`m_j = beta_j - ||L_j z + v_j||_2`。

合取取 min，析取取 max，或按逻辑 DAG 递归计算。训练可用平滑替代，最终评估必须使用准确的 min/max，并报告近似训练与实际判定不一致。

边界 margin 可用于诊断排序，但不是概率；锥残差不是精确欧氏距离。跨类型归一化需开发集固定，不能按测试标签调节。

不确定动作可用多个候选或集合包络。对半空间可以准确检查简单包络的最不利值；锥与分支使用经证明有效的上界/逐候选检查。不得将有限候选覆盖说成真实效果必然覆盖。若每候选都属于并集即可，不能错误要求所有候选进入同一分支。

覆盖不确定或依据不足时 NEED_EVIDENCE。明显违反且非缺证据时 BLOCK。低置信拒答必须参与效用、覆盖率与成本统计。

### 4.5 防止伪几何

以下测试为必需：

1. 同上下文多个候选共用区域。
2. 同约束在不同工具/调用上有稳定语义。
3. 每条违反标签由对应 margin 预测，不仅最终 min 正负正确。
4. 删除/改变一个条款主要影响对应边界与相关判定；无关条款变化不随意改变其他条件。
5. 干预或交换区域参数会按约束语义改变判定。
6. 比较无几何直接分类器和相同预算的 learned predicate backend。

单纯分类准确率不证明存在有价值的几何结构。潜空间坐标具有重参数化自由度，不能未经轴级监督解释某一维就是“授权强度”。

## 5. benchmark 获取、任务协议与分布隔离

官方来源（执行时读取具体版本文档和许可，固定 commit/package/data hashes）：

| 环境 | 用途 | 官方来源 |
|---|---|---|
| AgentDojo | 不可信工具内容、注入、安全—效用 | https://github.com/ethz-spylab/agentdojo |
| ToolSandbox | 状态依赖、多轮查询与交互 | https://github.com/apple-aiml-research/ToolSandbox |
| tau2-bench | 领域政策、对话、数据库效果 | https://github.com/sierra-research/tau2-bench |
| AppWorld | 跨应用、多 API、组合工具迁移 | https://github.com/StonyBrookNLP/appworld |

不要假设这些 benchmark 原生提供完整逐步安全标签或统一政策；必须做 availability audit。原生任务成功、额外研究政策违规、攻击目标成功分别报告。研究新增政策属于扩展协议，不冒称官方原生安全评价。

tau2 的参考动作通常只是得到目标最终状态的一条路径，不能把其他轨迹都标成违反。AppWorld 若使用代码 Agent，拦截实际 API 调用；避免多调用脚本整体放行后的中间效果逃逸。所有效果均在隔离的 benchmark 沙箱内，不连接真实邮件、银行或业务账户。

固定一个外部测试环境（建议 AppWorld，在确认可合法使用且适配后），其任务、轨迹、模型输出不得进入训练、提示示例或模型选择。若不适配，先记录原因并在看模型测试结果前更换冻结环境。

剩余环境按工具族/领域建立研究训练、开发、内部冻结测试；随后进行至少一次 leave-one-environment-out 复核。严格遵守各环境官方 train/test 限制，不把受限制的官方测试数据用于训练。某环境无官方训练集时，研究切分须明确披露，不能声称同其官方排行榜协议完全一致。

对工具规格、政策、任务模板、状态和反事实组做跨 split 去重。相同 seed task 的全部变体属于同一 split。大模型预训练是否见过公开 benchmark 通常未知；披露这一限制，通过新生成且冻结的工具组合/政策任务补充测试，不能宣称绝对无污染。

## 6. 数据生成与标签核验

### 6.1 数据单位

一条 boundary sample 保存可见前缀、提议动作、环境快照引用、政策、适用约束、证据关系、语义判定、执行效果、任务进展和标签来源。

模型输入与 gold/evaluator 状态物理分离存储。建立自动测试确认序列化后的输入不含隐藏目标、攻击目标、参考未来动作、gold role map 或标签。

### 6.2 收集不同 planner 的真实轨迹

用至少两种不同能力/家族的 planner 采集成功、失败、受攻击、缺证据及不同合法路径。单步候选评估时从同一前缀快照恢复，保证候选比较不是在前一次副作用之后执行。

不能只保留成功任务；不能只把出现攻击词的调用作为负例。记录查询操作的访问约束，不能默认 read-only 均安全。

### 6.3 监督组合

1. 环境 oracle：类型、对象存在性、金额、版本、状态更新、预算消耗等可验证事实。
2. 政策标注：由教师模型抽取，再由独立模型/方法复核，对冲突及高风险例外人工审核。
3. 效果与证据：引用具体字段/原文/事件；引用存在并不证明推理正确。
4. 目标支持：区分最终目标操作、必要前置步骤、无关操作。不是所有合法步骤都必须立即完成目标。
5. UNKNOWN：信息不足、政策有歧义、工具效果不可确定时保留未知。

标注来源按 oracle / human / adjudicated-teacher / unverified-teacher 分类，分层报告效果。不能把未验证教师标签叫 ground truth。建立独立、人工核验的关键语义测试集。

### 6.4 反事实与不变性组

- 对象/接收者/金额/时间的最小修改。
- 同值不同来源、同请求不同授权范围。
- 政策否定、例外、合取、析取及量词变化。
- 删除前置读取、读取失败、状态 stale、撤销授权。
- 历史累计消耗变化及跨工具信息流组合。
- 工具/字段改名、描述改写、字段顺序变化。
- 长历史插入无关内容及相近但不同实体。
- 伪造批准、工具规格/描述注入、返回内容中含指令。

每个干预重新核验标签，不继承原标签。困难负例既要破坏可行性，也要有语义相近却仍合法的例子，避免模型将任何改动都视为危险。

### 6.5 规模与费用

先跑有限规模的管线正确性与成本测量，不以 smoke 结果代替最终证据。正式训练规划范围：约 1–3 万条独立任务轨迹，20–50 万 boundary samples（含配对变体），实际由任务覆盖、标注质量、学习曲线与授权预算决定。这是规划区间，不是承诺已有数据或必须耗尽配额。

公开任务数少时不能通过大量改写伪装成独立任务。报告独立任务、工具族、状态、反事实组和总行数。

对每轮 API 用量记录输入/输出 token、缓存、重试、价格版本和累计费用；生成器断点续跑、内容去重、幂等调用；预算控制器应在发起下一批前检查额度。GPU 按卡时记录；不要拍脑袋承诺成本和训练时间。

## 7. 训练流程

### 7.1 选择模型与工程栈

根据 GPU 实测选择 7B–14B 级开放权重指令模型作为初始候选；必须核查许可、上下文支持、数值精度及可微调能力。最终模型选择在开发集完成。先验证 LoRA/部分解冻与几何头，资源足够且开发证据表明有收益时扩大解冻，不默认最大模型最佳。

几何头从 hidden states 输出实数 tensor，不依赖语言模型逐位生成浮点字符串。约束语义/证据可通过结构化 decoder 辅助输出，实数几何与语义约束槽位对齐。

固定 Python/CUDA/PyTorch/训练库版本，检查硬件支持后生成 lock 与环境记录。不得照抄未经服务器核验的安装命令。

### 7.2 训练课程（同一个最终模型的训练阶段）

A. 语义与证据：训练效果描述、适用约束覆盖、证据链接及 unknown；保留预训练语义能力。

B. 联合几何：训练动作点、约束区域及每条 margin，混合语义辅助任务，避免只学最终分类捷径。

C. 反事实与迁移：强化安全关键区别、改写不变性、跨工具关系一致性与动态转换。

D. 闭环错误采集：在训练环境运行 student，将误阻断、危险放行、遗漏、过度澄清和状态失效错误重新标注后加入训练。仅使用训练/开发环境，冻结测试不回流。

E. 开发集校准、冻结模型/阈值/提示/编译逻辑，随后最终测试。

### 7.3 损失

`L = lambda_c L_coverage + lambda_m L_membership + lambda_cf L_counterfactual + lambda_i L_invariance + lambda_r L_recovery + lambda_t L_temporal + lambda_u L_unknown + lambda_b L_capacity`。

- coverage：条款与分支、字段作用域、例外、条件的覆盖；对约束集合做匹配，避免输出排序成为标签。
- membership：每条约束满足/违反监督和最终几何结果；只用 episode success 不够。
- counterfactual：相关干预改变正确 margin/判定；无关干预保持。
- invariance：改名、改写、等价接口的判定与关系对齐。不能强迫两种效果仅因工具用途相似就完全同点。
- recovery：从表示恢复随机选取的关键关系/条件/值，不只恢复手挑容易字段。
- temporal：前置完成、失败、失效、撤权和累积效果变化。
- unknown：缺证据/歧义监督及经开发集校准的拒答。
- capacity：槽位/检索成本；安全信息损失优先于压缩，先比较无容量限制对照。

精确数值约束、ID 区分等不能靠语义相似损失代替；可加入通用数值编码/算术模块并学习调用，但不得新增 per-tool 金额规则。记录它们参与最终判定的方式。

### 7.4 校准与不确定性

先以有限多候选/ensemble disagreement 和语义 unknown supervision 实现，开发集评估风险—覆盖曲线。复杂包络只有在可证明计算有效且实测有收益时使用。

可采用独立校准集选择阈值；若使用统计覆盖方法，明确 exchangeability/分布假设，不能将同分布保证推广为未知环境或自适应攻击保证。

校准的目标包含高效用，不能靠无限澄清或全部拒绝达到低风险。限制澄清预算并按任务真实评分。

## 8. 验证矩阵、基线与统计

### 8.1 强基线

1. 原有 deterministic DAFR，仅按其真实协议运行。
2. 同骨干、同输入、相近 token/计算预算的直接 LLM checker。
3. 固定字段/独立阈值规则；不得刻意选择明显不合理阈值。
4. 相同编码和相同约束对象的 equivalent arithmetic predicate。
5. 相同编码器的非几何判定头，控制表示收益与几何收益。
6. gold 约束/证据输入上界，分解抽取、表示和读出错误。

如进一步做动作搜索/修复，Geometry 与 Predicate 必须共享候选集合、目标保持检查、搜索预算及状态。原始点投影未必对应真实调用，不把 latent projection 直接算 executable repair。

### 8.2 消融

历史来源/时间去除、单轮输入、固定与自适应容量、无反事实训练、无约束覆盖监督、半空间与锥、无分支、冻结状态、只累积不失效、各 d、无证据恢复、候选独立区域的约束一致性。

### 8.3 指标

映射：关键条款遗漏、字段作用域/否定例外准确率、证据关系准确率、精确实体与数值区分、UNKNOWN 的风险—覆盖、反事实正确率、改写一致性。

几何：每条约束成员关系准确率、分支正确率、normalized margin 分布、固定上下文区域一致性、与等价 predicate 分歧、数值错误。

运行：不安全放行率、良性误阻断、NEED_EVIDENCE 率、任务成功/utility、原生攻击成功、研究政策违规、澄清轮数、P50/P95 延迟、token/API/GPU 成本。

动态：前置完成后正确恢复、失效后错误放行、伪造授权导致权限变化、累计预算违规。

迁移：冻结模型未见工具族、未见环境、组合工具、长历史。训练分布指标与 OOD 指标分别报告。

标签独立性：模型标签与 oracle/human 标签分开评分。任务成功不能代替逐步政策合规。

### 8.4 统计与报告

主要比较使用相同任务/planner seeds 的配对结果，按独立任务或环境聚类计算区间；反事实行不是独立样本。至少三个训练随机种子评估稳定性，推理 seeds 按 benchmark 协议固定并披露。

零攻击成功必须带分母、攻击集合、来源条件及区间，不写成绝对安全。测试集不能反复用于调 prompt、lambda、阈值或几何容量。发现失败后可启动新开发周期，但旧测试已成为开发信息，新最终主张需要新的冻结测试。

## 9. 验收标准与决策

以下为预注册的工程质量目标，不是保证或已有结果。正式数值在数据可用性和标签可靠性审计后、看最终测试结果前固定。

必须通过：

- 输入/gold 隔离；候选不泄漏到区域路径；来源权限不因外部文本改变；动态失败/失效状态正确处理。
- 所有几何判定可从保存的点和参数精确重算；equivalent predicate 分歧为零或仅限事先定义的浮点容差且逐例解释。
- 正常步骤、必要查询和多条合法路径被正确处理；无权限扩大和真实外部副作用。
- 可从 clean 环境恢复工程、模型和评估；历史结果不被新结果覆盖。

研究效果门槛：

- 映射细粒度效果明显优于固定字段规则，并相对于同骨干强 checker 有可解释的效用/风险/成本收益。
- 未见环境维持有意义的任务效用；低违规不能主要来自全拒绝或超量澄清。
- 与高容量对照相比，压缩表示在关键语义与执行判定上的差距小，给出区间和 worst-group 结果才使用“近乎无损”。
- 几何的独立价值由 matched tests 支持。若与 equally instrumented predicate 持平，承认等价，贡献收缩为共享映射和动态执行表示；不能靠换弱基线挽救结论。

如果未达到门槛：交付失败分类、训练诊断、成本与下一步可验证修改；不要称完成效果目标，也不要无限追加成本。不能通过删除困难任务、隐藏未知或事后换指标制造成功。

## 10. 工程目录、接口与测试

建议结构：

```text
src/dafr_mapper/
  schemas.py                 # input/output/constraint/state schemas
  context.py                 # visible-context serialization & source boundaries
  model.py                   # shared backbone, adaptive memory, action/region paths
  geometry.py                # halfspace/cone/logical composition
  checker.py                 # exact membership & three-way decision
  runtime.py                 # before-call / after-result hooks
  data/                      # adapters, labeling, interventions, split audit
  training/                  # losses, trainer, calibration
  evaluation/                # metrics, baselines, paired evaluation
configs/unified_mapper/
scripts/unified_mapper/
tests/unified_mapper/
data/unified_mapper/manifests/ # hashes/provenance/splits, no secrets
results/unified_mapper/        # run manifests and aggregate reports
docs/unified_mapper/
```

实现以下 CLI 能力（名称可调整，完成后必须给出真实可运行命令，不冒称当前已存在）：

```text
doctor → inspect_resources / providers / benchmark versions
collect → capture sandbox trajectories with budget & resume
label → oracle + teacher + adjudication
audit → split leakage / hidden-state leakage / policy coverage
train → staged training from pinned config
calibrate → dev-only thresholds
evaluate → frozen boundary and closed-loop tests
serve → unified pre-execution mapper/checker
reproduce → rebuild aggregates from raw records
```

高优先级测试：候选替换不变区域、三值判定、逻辑分支、参数合法性、精确数值、来源伪造、失败调用、版本失效、累计预算、长上下文遗漏、日志不含密钥、断点幂等、并发环境隔离、CPU/GPU 数值差异。

现有测试按仓库配置运行一次建立基线；每次相关实现修改运行匹配测试及必要回归，不无目的重复全量长实验。

## 11. 资源配置与作业管理

服务器实际配置由执行者核验，不假定当前聊天中的 macOS 路径在服务器存在。

资源表需要：GPU 型号/数量/显存、CUDA、磁盘、工作目录、调度器/可用卡时；教师与裁判 API 的可用模型/endpoint/凭据位置；最大输入上下文、费用与并发；训练骨干本地路径或可下载来源。

配置只存凭据环境变量名称，不存值。建议 `teacher_model`、`judge_model`、`planner_models`、`student_model`、`api_token_budget`、`api_cost_cap`、`gpu_hour_cap`、`max_concurrency`、`disk_cap_gb`、`deadline`、`deployment_latency_target`。额度未指定时字段为 null 并显式阻止大规模作业。

不用已有 session 临时 /tmp 工具或凭据作为服务器前提。GitHub 私有仓库认证使用服务器已有授权；缺失时让用户在服务器配置，不从本聊天提取 token。

训练和采集使用服务器支持的调度器/持久作业机制；定期写 checkpoint、进度、费用与 job id。进程结束、失败、磁盘不足及额度耗尽要正确退出。不要把挂着的进程称为已经完成实验。

报告 ETA 应根据实测 examples/sec、rollout throughput、teacher latency 和 remaining count；提供范围，不把资源规划当作实测结果。

## 12. 执行顺序与每个阶段的产物

1. 资源与仓库审计：`resource_report`、`baseline_commit`、旧测试状态、预算配置。
2. 冻结实验协议：数据来源/许可、split、label taxonomy、指标/阈值选择规则、baseline 和费用计划。
3. 环境接口和数据管线：沙箱恢复、pre/post hooks、输入/gold 分离、失败恢复测试。
4. 监督质量核验：独立关键语义集、标注一致性/错误表、数据 manifest。
5. mapper 与几何实现：候选独立区域、共享空间、可学习容量、checker、数值与来源测试。
6. 完成训练课程与训练环境闭环错误补充；记录每次开发改动，不接触冻结测试。
7. 开发校准后冻结：模型 hash、配置 hash、数据 hash、代码 commit、校准 artifact。
8. 独立运行最终测试、matched baselines、迁移与 ablations；不再调参。
9. 交付模型、运行服务、复现命令、结果报告、失败分析及方法论文素材。

每次进度报告写清已完成产物、实测结论、剩余不确定性和下一作业；不只输出计划。只在最终验收或明确外部阻塞时交接，不把等待作业等同研究完成。

## 13. 最终交付

- 可加载的 mapper checkpoint、tokenizer、geometry heads、校准参数。
- 统一 runtime API、服务器推理服务与接入示例。
- 数据构建、训练、评估与复现命令，以及锁定依赖。
- 数据/模型/代码的 provenance 与 hashes。
- 未见环境结果、细粒度语义测试、强基线和几何独立贡献分析。
- 不安全放行、误阻断、未知、延迟/成本的完整失败表。
- 无手写 per-tool 映射的审计；确有特殊适配时列出并统计配置成本。
- 论文可用的方法说明与证据表，只写已测量结论；不要直接改写现有主结果。

## 14. 相关研究比较要求

正式确定 novelty 前读取并比较：

- Progent：<https://arxiv.org/abs/2504.11703>，策略生成、动态权限控制。
- CaMeL：<https://arxiv.org/abs/2503.18813>，数据/控制流与 capability。
- Schema-Guided Dialogue：<https://arxiv.org/abs/1909.05855>，描述驱动未见服务迁移。
- Safe Exploration in Continuous Action Spaces：<https://arxiv.org/abs/1801.08757>，安全层动作纠正。

这些工作已涵盖若干组成部分。候选贡献是“统一逐调用、执行相关语义保持的可学习映射 + 多轮动态共享几何”，能否成立取决于独立实验与更完整的文献比较。不能宣称任意规则程序不能表达相同边界，也不能将保存 margin 的检查当作新运行安全证明。

## 15. 可直接复制到新窗口的启动指令

> 请读取我附上的《统一可学习工具调用—约束映射器：服务器完整执行方案》，并按其完成研究工程。项目仓库是 https://github.com/Lwind-Liu/DAFR-AAAI2027-private，起始分支 jianghao。目标是在每轮执行前，用统一可学习 mapper 将工具调用与上下文映射为高维动作点，将任务/政策/状态映射为候选独立的动态可行域；信息保留和关系构建由训练学习，不逐工具手写配置。你负责 benchmark 寻找与接入、数据、标注、模型、训练和独立评估。先核验服务器已有 API/GPU/仓库与预算配置，立即完成不依赖缺失资源的工作；缺少额度时提供实测费用规划后询问，不能启动无上限作业。完整阅读文档后执行，不只回复计划。历史 DAFR 结果不能作为新方法成绩；冻结测试不回流训练；最终判定必须实际来自几何检查，并保留同等信息和预算的强基线。

仅复制此启动段落不足以传递全部技术细节，必须同时提供本文件全文或文件附件，或让服务器读取仓库 `jianghao` 分支中本文件的最新版本。交接文件位于 `docs/experiments/`，旧 checkout 需要先同步远端并确认文件存在。
