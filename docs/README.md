# JobMatch Hub

招聘信息聚合与简历匹配系统 MVP。它不接入真实招聘平台爬虫，先支持 CSV、JSON 和手动 JD 文本导入，避免反爬、账号风控和合规问题，同时保留了后续对接数据源的边界。

## 能力

- 从简历和 JD 中提取 Java、Spring Boot、Redis、PostgreSQL、Docker、LLM、RAG、React、Kafka、Kubernetes、Prometheus、CI/CD 等技能关键词。
- 按技能覆盖、经验关键词、业务领域匹配和加分项计算匹配分。
- 输出 matched_skills、missing_skills、priority、定制投递话术和简历优化建议。
- 同时提供 CLI 和 Linear 风格 Web UI。
- 生成 JSON 结果和 Markdown 报告，便于放进投递记录或面试作品集。

## 运行

在仓库根目录执行：

```bash
python -m jobmatch_hub score --resume jobmatch-hub/examples/resume.md --jobs jobmatch-hub/examples/jobs.csv --out jobmatch-hub/out
python jobmatch-hub/tests/smoke_test.py
python -m jobmatch_hub web --host 127.0.0.1 --port 8788
```

Web UI 打开 `http://127.0.0.1:8788`。

## CSV 格式

`examples/jobs.csv` 使用以下字段：

```csv
id,title,company,location,description
```

JSON 可以是数组，也可以是 `{ "jobs": [...] }`，字段同 CSV。

## 面试亮点

- 真实产品取舍：先做合规的数据导入和本地分析，不伪装成不稳定爬虫。
- 结构清晰：`analyzer.py` 负责领域算法，`report.py` 负责输出，`cli.py` 和 `web.py` 只是入口层。
- 可解释算法：分数由技能、经验、领域和加分项组成，结果能解释为什么推荐或暂缓投递。
- 可扩展边界：未来可以把岗位源、技能词典、权重策略和 LLM 改写模块替换成独立插件。
