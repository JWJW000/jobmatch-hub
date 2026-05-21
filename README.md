# JobMatch Hub

招聘信息聚合与简历匹配系统：导入简历和岗位 JD，提取技能关键词，计算匹配度、缺失技能、投递优先级，并生成定制投递话术和简历优化建议。

## Run

```bash
python docs/tests/smoke_test.py
python -m jobmatch_hub score --resume docs/examples/resume.md --jobs docs/examples/jobs.csv --out docs/out
python -m jobmatch_hub web --host 127.0.0.1 --port 8788
```

## Features

- 简历/JD 技能关键词提取
- 匹配分、技能缺口、投递优先级
- Markdown + JSON 报告
- Linear/Open Design 风格暗色 Web UI
- 无复杂依赖，Python 标准库优先
