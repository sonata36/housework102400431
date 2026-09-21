# 计算机视觉顶会论文热点分析平台

- 学号：102400431
- 课程：[福州大学软件工程实践](https://bbs.csdn.net/forums/2601_CS_SE_FZU)
- 作业：[作业要求](https://bbs.csdn.net/topics/620526318)
- CodeArts：[102400431 仓库](https://codehub.devcloud.cn-north-4.huaweicloud.com/aa98a236e6c942349d6fb7dc270d27eb/102400431.git)
- 代码规范：[codestyle.md](codestyle.md)

## 当前状态

第四轮已完成第一版本地核心功能：SQLite 论文管理、单篇/批量字段导入、精确和模糊检索、论文详情、覆盖数/覆盖率 Top 10、关键词节点图谱、趋势接口和 ECharts 页面。第三轮专用工具原型仍暂缓，不能用本项目页面代替专用工具原型；尚未部署云服务器。

平台支持 CVPR、ICCV、ECCV 论文的本地单篇/批量字段导入、列表管理与在线索引查询、Top 10 方向、关键词节点图谱、多年跨会议趋势动画。技术栈为 Python、Flask、SQLite、HTML/CSS/JavaScript、ECharts；ECharts 当前从 jsDelivr CDN 加载，离线环境下图表可能无法显示。

## 本地运行

需要 Python 3.11 或更高版本；当前机器使用 Python 3.14，其他版本尚未验证。建议使用独立虚拟环境。

Windows PowerShell，在本目录执行（如果 python 不在 PATH，请用已安装解释器的完整路径）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m flask --app run.py init-db
.\.venv\Scripts\python.exe run.py
```

Linux/macOS：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python run.py
```

打开 http://127.0.0.1:5000/ 。健康检查为 http://127.0.0.1:5000/health ，应返回 `{"status":"ok"}`。该接口仅说明 Web 进程可响应，不代表论文数据或外部服务可用。

首次体验统计和趋势页面时，可在 `项目` 目录执行下面的命令导入 15 篇本地原型样本：

```powershell
.\.venv\Scripts\python.exe -m flask --app run.py seed-demo
```

该命令具有幂等性，重复执行不会重复插入相同样本。样本的 `source` 为 `prototype_sample`，用于界面和统计流程验证，不是从 CVPR、ICCV 或 ECCV 官网采集的真实数据。需要空数据库时，可删除本地 `instance/papers.sqlite3` 后重新执行 `init-db`；该文件不会提交到 Git。

本机已创建 `.venv` 时可跳过创建。依赖范围声明在 `requirements.txt`，首次安装的具体版本保存在 `requirements-lock.txt`。它是版本快照，不是含哈希的供应链锁文件；更改依赖后重新验证并更新快照。

PyCharm：打开本目录，设置已有解释器为 `.venv/Scripts/python.exe`，右键运行 `run.py`，工作目录设为项目根目录。无需 PyCharm 专业版的 Flask 运行配置。图文材料与详细指南位于同级 `其他/`，代码运行不依赖该文件夹。

运行入口绑定本机地址且关闭调试；仅供本地开发。云端部署时另行配置生产 WSGI 服务、进程管理和网络访问。

## 目录与设计

```text
app/
  __init__.py          # 应用工厂：创建 Flask 实例并注册路由
  routes.py            # 总览、统计说明、健康检查
  paper_routes.py      # 论文管理和联网失败接口
  import_routes.py     # 单篇/批量导入
  analytics_routes.py  # Top 10、图谱和趋势接口
  db.py                # SQLite schema 与连接
  services.py          # 业务服务
  sources.py           # 在线索引与 CVF Open Access 来源适配器
  templates/           # 页面模板
  static/css/base.css
run.py                 # PyCharm 可直接运行的入口
requirements.txt       # 直接依赖范围
requirements-lock.txt  # 验证时实际安装的版本
codestyle.md
```

`create_app()` 集中配置数据库、注册 Blueprint 并执行幂等建表。`db.py` 管理 SQLite 连接和外键 schema；`services.py` 放标题/关键词归一化、论文 CRUD、批量导入和统计；`sources.py` 负责离线索引查询和 CVF Open Access 适配；`paper_routes.py`、`import_routes.py`、`analytics_routes.py` 分别处理论文、导入和分析页面/API。模板和样式分别维护，`if __name__ == "__main__"` 保证导入入口时不会自动启动开发服务器。

## 已实现功能与边界

- 论文管理：新增、编辑、删除、详情、分页，以及标题精确和标题/编号/会议/关键词模糊检索。
- 导入：单篇和多行批量导入逐条处理；重复、字段缺失和失败不会阻止其他项保存。
- 分析：按会议和年份筛选论文覆盖数/覆盖率 Top 10；关键词图谱返回节点并支持点击过滤；趋势页面支持会议、年份、关键词和重播控制。
- 数据状态：趋势接口区分未举办、未采集和有样本但关键词零出现。
- 在线查询：`/papers/online-lookup` 从 `online_papers` 索引表按标题精确或模糊匹配，并展示摘要、关键词和原文链接；未命中时返回可重试的失败页。
- 真实抓取：导入页支持使用完整标题访问 CVF Open Access 年度目录，成功后保存论文并跳转详情页；JSON 接口为 `POST /import/fetch-cvf`。该适配器依赖公开页面可访问性，不能代表所有年份和所有来源都稳定可用。

当前版本增加了 CVF Open Access 会议目录和论文详情页的真实标题抓取适配器，支持 CVPR、ICCV、ECCV 的公开目录范围（默认扫描 2020—2026）。抓取结果会解析标题、作者、摘要、会议、年份、原文链接和轻量抽取关键词，并保存到本地数据库。网络超时、页面缺失、字段缺失和标题不一致会返回明确失败或缺失字段状态，不生成论文结果。仍未实现文件上传、云端部署、用户登录和第三轮专用原型发布；本地 `online_papers` 索引继续用于离线模糊查询。作者关键词与轻量抽取关键词分开保存；自动抽取只是透明的英文词频回退方案，不代表学术关键词质量评估。图谱关系边当前表示同一论文中的关键词共现。在线查询未命中时，浏览器返回 HTML 失败页，JSON 客户端仍可读取 503 结果。

## 测试

在 `项目` 目录执行：

```powershell
.\.venv\Scripts\python.exe -m compileall -q app run.py tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

当前测试覆盖重复标题、精确/模糊检索、批量部分成功、关键词归一化、Top 10、趋势状态、关键页面以及在线查询命中和未命中。尚未覆盖浏览器端视觉回归、并发导入、云端部署和 CDN 不可用时的图表降级。

## 数据来源

真实抓取来源为 [CVF Open Access](https://openaccess.thecvf.com/)，当前适配器按 CVPR、ICCV、ECCV 年度目录查找标题，再读取详情页。默认年份为 2020—2026，实际可用范围受网站目录结构、网络访问和请求限制影响。不能假定 DBLP 包含论文摘要；算法抽取关键词将与原文关键词区分。离线 `online_papers` 索引仍用于无网络时的演示查询，不能与真实抓取结果混为一谈。

## AI 使用说明

用户登记工具：ChatGPT；具体模型/版本待用户根据界面核实。第一轮源代码、页面样式和初始文档由 AI 根据用户需求生成，并由 AI 执行环境及运行验证；用户提供目标、范围、目录约束和基础信息。尚未记录用户对本轮代码的人工修改、理解或审查，不将其声明为已完成。

人工复审后应更新真实分工；后续每个重要模块保留提示词、输出摘要、修改理由和验证结果。过程材料放在同级 `其他/`，该路径只在本机目录安排中存在，不属于远程仓库代码内容。

## 版本管理与后续交付

项目代码使用 main 和 dev 分支，初始化时两者采用同一个项目骨架。后续在 dev 开发，基础功能和复审完成后通过 PR 合并 main，再发布 1.0.0 Release；当前骨架不作为正式版本发布。

远程原有 master 仅含初始化内容（用户说明），保留该分支。在 CodeArts 查看本项目时选择 main 或 dev；若网页默认仍显示 master，请切换分支。推送采用正常分支更新，不强制覆盖远程历史。虚拟环境、缓存和本地数据由 .gitignore 排除，博客和截图按约定保存在本机“其他”目录。

待补充：专用工具原型链接、云端访问地址、博客链接、Release 页面和更多年份来源验证。
