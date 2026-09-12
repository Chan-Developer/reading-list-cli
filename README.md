# 阅读清单管理器

一个只使用 Python 标准库的本地命令行工具，用 JSON 文件维护待读文章。

## 运行

需要 Python 3.10 或更高版本（使用了标准库类型标注语法）。无需安装第三方依赖；在项目根目录执行：

```bash
python3 -m reading_list --help
```

默认数据文件是当前目录下的 `.reading_list.json`。用全局 `--data-file PATH` 可指定其他位置。

## 命令示例

```bash
# 添加文章；tags 是可选的逗号分隔标签
python3 -m reading_list add "Python argparse" "https://docs.python.org/3/library/argparse.html" --tags python,cli

# 使用指定的数据文件添加和列出
python3 -m reading_list --data-file my-list.json add "JSON 标准库" "https://docs.python.org/3/library/json.html"
python3 -m reading_list --data-file my-list.json list

# 筛选：可按状态、按精确标签，或叠加两者（结果按 id 递增）
python3 -m reading_list list --status unread
python3 -m reading_list list --tag python
python3 -m reading_list list --status done --tag cli

# 从 JSON 数组导入（会报告导入和跳过的数量）
python3 -m reading_list import articles.json

# 标记已读、删除条目、查看统计
python3 -m reading_list done 1
python3 -m reading_list remove 1
python3 -m reading_list stats
```

`add` 的 URL 必须是带主机名的完整 `http://` 或 `https://` 地址。命令缺少参数、URL 不合法、id 不存在或数据 JSON 损坏时，程序会输出清晰错误信息并以非零状态退出。

## 导入格式与限制

`import FILE` 只接受顶层为 JSON 数组的文件。数组内每个对象都必须有非空字符串 `title` 和合法 `http://` 或 `https://` 字符串 `url`；可选的 `tags` 必须是字符串数组。可以出现其他字段，但它们不会被导入；新条目一律作为未读保存。

导入文件有任何一项不合法时，命令会报告该项的数组下标并且**不会改动**当前数据文件。URL 会与现有条目及同一导入文件中更早的条目比较；重复 URL 将跳过，不会创建重复条目。

例如 `articles.json`：

```json
[
  {
    "title": "Python argparse",
    "url": "https://docs.python.org/3/library/argparse.html",
    "tags": ["python", "cli"]
  }
]
```

## 数据格式

数据采用 UTF-8 JSON，程序会在首次写入时创建文件。示例：

```json
{
  "next_id": 2,
  "items": [
    {
      "id": 1,
      "title": "Python argparse",
      "url": "https://docs.python.org/3/library/argparse.html",
      "tags": ["python", "cli"],
      "done": false
    }
  ]
}
```

`next_id` 供程序分配下一个不重复 id；请避免在程序运行时手动编辑数据文件。

## 测试

```bash
python3 -m unittest discover -v
```
