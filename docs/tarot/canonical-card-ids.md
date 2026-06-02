# 78 张塔罗 `canonical_card_id` 命名清单

## 1. 目标

这份清单用于定义塔罗资源系统里的标准卡牌 ID，供以下场景统一复用：

1. 图片文件命名
2. `card.yaml` 文件命名
3. 抽牌结果存储
4. Prompt 上下文构建
5. 前后端资源关联

## 2. 命名规则

统一规则：

1. 大阿尔卡那：`major.<序号>.<英文slug>`
2. 小阿尔卡那数字牌：`minor.<suit>.<序号>.<英文slug>`
3. 小阿尔卡那宫廷牌：`minor.<suit>.<序号>.<court_name>`
4. 不在 ID 中包含语言信息
5. 不在 ID 中包含正位 / 逆位信息

花色约定：

1. `cups`
2. `wands`
3. `swords`
4. `pentacles`

## 3. 大阿尔卡那（22 张）

| 序号 | 中文名 | 英文名 | canonical_card_id |
| --- | --- | --- | --- |
| 0 | 愚者 | The Fool | `major.00.fool` |
| 1 | 魔术师 | The Magician | `major.01.magician` |
| 2 | 女祭司 | The High Priestess | `major.02.high_priestess` |
| 3 | 皇后 | The Empress | `major.03.empress` |
| 4 | 皇帝 | The Emperor | `major.04.emperor` |
| 5 | 教皇 | The Hierophant | `major.05.hierophant` |
| 6 | 恋人 | The Lovers | `major.06.lovers` |
| 7 | 战车 | The Chariot | `major.07.chariot` |
| 8 | 力量 | Strength | `major.08.strength` |
| 9 | 隐者 | The Hermit | `major.09.hermit` |
| 10 | 命运之轮 | Wheel of Fortune | `major.10.wheel_of_fortune` |
| 11 | 正义 | Justice | `major.11.justice` |
| 12 | 倒吊人 | The Hanged Man | `major.12.hanged_man` |
| 13 | 死神 | Death | `major.13.death` |
| 14 | 节制 | Temperance | `major.14.temperance` |
| 15 | 恶魔 | The Devil | `major.15.devil` |
| 16 | 高塔 | The Tower | `major.16.tower` |
| 17 | 星星 | The Star | `major.17.star` |
| 18 | 月亮 | The Moon | `major.18.moon` |
| 19 | 太阳 | The Sun | `major.19.sun` |
| 20 | 审判 | Judgement | `major.20.judgement` |
| 21 | 世界 | The World | `major.21.world` |

## 4. 圣杯（14 张）

| 序号 | 中文名 | 英文名 | canonical_card_id |
| --- | --- | --- | --- |
| 1 | 圣杯王牌 | Ace of Cups | `minor.cups.01.ace` |
| 2 | 圣杯二 | Two of Cups | `minor.cups.02.two` |
| 3 | 圣杯三 | Three of Cups | `minor.cups.03.three` |
| 4 | 圣杯四 | Four of Cups | `minor.cups.04.four` |
| 5 | 圣杯五 | Five of Cups | `minor.cups.05.five` |
| 6 | 圣杯六 | Six of Cups | `minor.cups.06.six` |
| 7 | 圣杯七 | Seven of Cups | `minor.cups.07.seven` |
| 8 | 圣杯八 | Eight of Cups | `minor.cups.08.eight` |
| 9 | 圣杯九 | Nine of Cups | `minor.cups.09.nine` |
| 10 | 圣杯十 | Ten of Cups | `minor.cups.10.ten` |
| 11 | 圣杯侍从 | Page of Cups | `minor.cups.11.page` |
| 12 | 圣杯骑士 | Knight of Cups | `minor.cups.12.knight` |
| 13 | 圣杯王后 | Queen of Cups | `minor.cups.13.queen` |
| 14 | 圣杯国王 | King of Cups | `minor.cups.14.king` |

## 5. 权杖（14 张）

| 序号 | 中文名 | 英文名 | canonical_card_id |
| --- | --- | --- | --- |
| 1 | 权杖王牌 | Ace of Wands | `minor.wands.01.ace` |
| 2 | 权杖二 | Two of Wands | `minor.wands.02.two` |
| 3 | 权杖三 | Three of Wands | `minor.wands.03.three` |
| 4 | 权杖四 | Four of Wands | `minor.wands.04.four` |
| 5 | 权杖五 | Five of Wands | `minor.wands.05.five` |
| 6 | 权杖六 | Six of Wands | `minor.wands.06.six` |
| 7 | 权杖七 | Seven of Wands | `minor.wands.07.seven` |
| 8 | 权杖八 | Eight of Wands | `minor.wands.08.eight` |
| 9 | 权杖九 | Nine of Wands | `minor.wands.09.nine` |
| 10 | 权杖十 | Ten of Wands | `minor.wands.10.ten` |
| 11 | 权杖侍从 | Page of Wands | `minor.wands.11.page` |
| 12 | 权杖骑士 | Knight of Wands | `minor.wands.12.knight` |
| 13 | 权杖王后 | Queen of Wands | `minor.wands.13.queen` |
| 14 | 权杖国王 | King of Wands | `minor.wands.14.king` |

## 6. 宝剑（14 张）

| 序号 | 中文名 | 英文名 | canonical_card_id |
| --- | --- | --- | --- |
| 1 | 宝剑王牌 | Ace of Swords | `minor.swords.01.ace` |
| 2 | 宝剑二 | Two of Swords | `minor.swords.02.two` |
| 3 | 宝剑三 | Three of Swords | `minor.swords.03.three` |
| 4 | 宝剑四 | Four of Swords | `minor.swords.04.four` |
| 5 | 宝剑五 | Five of Swords | `minor.swords.05.five` |
| 6 | 宝剑六 | Six of Swords | `minor.swords.06.six` |
| 7 | 宝剑七 | Seven of Swords | `minor.swords.07.seven` |
| 8 | 宝剑八 | Eight of Swords | `minor.swords.08.eight` |
| 9 | 宝剑九 | Nine of Swords | `minor.swords.09.nine` |
| 10 | 宝剑十 | Ten of Swords | `minor.swords.10.ten` |
| 11 | 宝剑侍从 | Page of Swords | `minor.swords.11.page` |
| 12 | 宝剑骑士 | Knight of Swords | `minor.swords.12.knight` |
| 13 | 宝剑王后 | Queen of Swords | `minor.swords.13.queen` |
| 14 | 宝剑国王 | King of Swords | `minor.swords.14.king` |

## 7. 星币（14 张）

| 序号 | 中文名 | 英文名 | canonical_card_id |
| --- | --- | --- | --- |
| 1 | 星币王牌 | Ace of Pentacles | `minor.pentacles.01.ace` |
| 2 | 星币二 | Two of Pentacles | `minor.pentacles.02.two` |
| 3 | 星币三 | Three of Pentacles | `minor.pentacles.03.three` |
| 4 | 星币四 | Four of Pentacles | `minor.pentacles.04.four` |
| 5 | 星币五 | Five of Pentacles | `minor.pentacles.05.five` |
| 6 | 星币六 | Six of Pentacles | `minor.pentacles.06.six` |
| 7 | 星币七 | Seven of Pentacles | `minor.pentacles.07.seven` |
| 8 | 星币八 | Eight of Pentacles | `minor.pentacles.08.eight` |
| 9 | 星币九 | Nine of Pentacles | `minor.pentacles.09.nine` |
| 10 | 星币十 | Ten of Pentacles | `minor.pentacles.10.ten` |
| 11 | 星币侍从 | Page of Pentacles | `minor.pentacles.11.page` |
| 12 | 星币骑士 | Knight of Pentacles | `minor.pentacles.12.knight` |
| 13 | 星币王后 | Queen of Pentacles | `minor.pentacles.13.queen` |
| 14 | 星币国王 | King of Pentacles | `minor.pentacles.14.king` |

## 8. 文件命名建议

建议直接使用 `canonical_card_id` 命名资源文件：

```text
major.00.fool.jpg
major.00.fool.card.yaml
minor.cups.05.five.jpg
minor.cups.05.five.card.yaml
```

## 9. 使用建议

建议把这份清单视为全局稳定常量：

1. 不随文案变化修改
2. 不随显示语言变化修改
3. 不随前端展示名称变化修改
4. 后续新增别名只加在元数据中，不修改主 ID
