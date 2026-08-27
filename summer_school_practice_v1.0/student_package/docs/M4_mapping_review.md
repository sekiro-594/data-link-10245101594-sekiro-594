# M4 AI 辅助映射核验说明

本模块使用课程提供的 `pre_generated_mapping_candidate.csv` 作为 AI 生成的候选结果。我没有直接使用候选表，而是逐项对照 `source_field_definitions.md`、`teaching_message_spec.md` 和统一字段定义，最后把确认后的规则写入 `verified_mapping_table.csv`。

## 核验时发现的问题

- 候选结果把纬度码和经度码对应的统一字段写反了。我根据协议中的字节位置，把 `latitude_code` 对应到 `position.lat`，把 `longitude_code` 对应到 `position.lon`。
- 高度字段不能直接使用协议中的整数值。只有有效位 bit2 为 1 时才进行 `altitude_code - 1000`，结果单位为米；无效时保持 null。
- `status_flags.bit2` 表示时间使用了最后联系时间作为回退，并不代表时间戳一定无效。因此该情况下 `time_source` 写成 `last_contact_fallback`，正数时间戳仍然可以通过时间有效性检查。
- 呼号需要先检查 `validity_flags.bit6`。该位为 1 时去掉末尾的 NUL 填充，为 0 时统一字段写成 null。
- `message_valid` 只表示 TeachingLink 帧通过了接收端检查，不能用它判断数据来源是否真实，也不能代替 M5 的异常检查。

## 我使用的验证方法

我重点检查了“真实的 0”和“字段缺失”是否会被混淆。目标 `000001` 的位置接近 0，垂直速度也是 0，但对应有效位为 1，所以这些值应正常保留。目标 `780def` 的经纬度有效位为 0，因此统一结果中经纬度保持 null，不能把协议中的占位整数 0 当成真实坐标。

最后，我将 OpenSky 和 TeachingLink 两类记录都转换成统一 NDJSON，并重新逐行解析。生成的 6 条记录都能正常读取，说明核验后的字段名称、层次和空值处理能够继续用于后续模块。

这些映射规则只针对课程给出的字段和 TeachingLink 教学协议，不代表真实装备或其他数据链协议的处理方式。
