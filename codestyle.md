# 代码规范

## 规范来源

- Python 官方 PEP 8：https://peps.python.org/pep-0008/
- Python 官方 PEP 257（文档字符串）：https://peps.python.org/pep-0257/
- Google HTML/CSS Style Guide：https://google.github.io/styleguide/htmlcssguide.html
- Google JavaScript Style Guide：https://google.github.io/styleguide/jsguide.html

以下为本项目选用的规则。尚未引入自动规范检查工具，不宣称已通过全部风格检查。

## Python

- 使用 UTF-8，4 个空格缩进，不混用制表符。
- 普通代码行尽量不超过 79 字符；注释和文档字符串尽量不超过 72 字符。
- 模块、函数和变量使用 snake_case，类使用 PascalCase，常量使用 UPPER_SNAKE_CASE。
- 导入通常分为标准库、第三方、本地三组；应用工厂内为延迟注册使用的本地导入需保持目的明确。
- 模块、公开函数写清晰的文档字符串，说明行为；复杂逻辑解释原因而非逐行翻译。
- 捕获具体异常，不使用裸 except 掩盖问题；错误信息不包含凭据。
- 路由处理请求与响应；后续数据获取、清洗和统计放入独立模块，避免堆在路由中。
- 数据库访问使用参数化查询；配置、路径通过标准库处理，不把本机绝对路径写入程序逻辑。

## 页面与脚本

- HTML/CSS/JavaScript 使用 2 个空格缩进；HTML 保留 lang、字符集与 viewport。
- 使用语义化标签，表单关联 label，反馈状态不能仅靠颜色表达。
- JavaScript 优先 const，需重新赋值时使用 let，不使用 var；语句保留分号。
- 不将不可信内容直接拼接进 HTML；模板默认转义，后续脚本更新文本优先使用 textContent。
- 样式和脚本独立存放；不把实际密钥放入客户端文件。

## 数据与协作（项目约定）

- 数据保留来源、年份、会议和抽取方式，缺失数据使用明确空值，不虚构摘要或统计值。
- 每次改动先运行适当验证，再做有意义的提交；提交正文注明真实 AI 参与和人工审查状态。
- 不在日志、仓库、截图中保留密码、私钥和访问令牌。
- 提交前检查 git diff；忽略环境、数据库运行文件和编辑器缓存，保留依赖声明。

## 第四轮实现补充

- 测试使用 Python 标准库 `unittest`，测试数据写入临时 SQLite 文件，不提交运行数据库。
- 路由只负责请求参数和响应，数据库查询、导入状态和统计口径集中在服务模块。
- 在线查询通过独立适配器访问 `online_papers` 索引表，避免把查询逻辑耦合到页面路由。
- Jinja 模板默认转义用户输入；前端脚本更新状态文字时使用 `textContent`。
