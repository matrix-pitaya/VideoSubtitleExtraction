# 任务数据协议 v1.0

`task-v1.schema.json` 固定字段：格式版本、任务 ID、标题、语言、状态、分段起止秒数和文本、可选错误码与说明。文件路径、来源链接、Cookies、订单信息和原始引擎错误不属于此公共协议。失败说明应脱敏。

`examples/task-v1.json` 是 Python 和 TypeScript 共用中文验收样例。秒数必须有限、非负、end > start、按时间排序且不重叠；无口播任务的 segments 为空。SRT 输出按最近毫秒取整，并正确处理进位。

`python_adapter.py` 可将现有工作台 item 转成协议任务；现阶段是独立适配器，没有修改工作台存储或导出行为。浏览器实现见 `versions/Browser/src/protocol.ts`。不承诺两个端的模型、OCR 或媒体解码实现可直接共享。

```powershell
python -m unittest discover -s protocol -p 'test_*.py'
```

浏览器任务状态由客户端生成，不能证明付费分钟、计费次数或识别成功。阶段 A 不发送任务状态到服务器；未来 API 必须按不可信输入处理，以服务端权益、幂等任务 ID 和原子事务决定预占、完成或释放，技术失败不能重复扣权益。
