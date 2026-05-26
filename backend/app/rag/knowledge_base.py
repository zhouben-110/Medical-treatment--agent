"""结构化疾病-症状知识库"""

DISEASE_KNOWLEDGE = [
    {
        "disease": "普通感冒",
        "symptoms": ["发热", "咳嗽", "流涕", "鼻塞", "头痛", "乏力", "咽痛", "打喷嚏"],
        "description": "由鼻病毒、冠状病毒等引起的上呼吸道感染，是最常见的急性呼吸道疾病。",
        "treatment": "对症治疗为主：退热药（对乙酰氨基酚）、止咳药、多休息、多饮水。不推荐常规使用抗生素。",
        "when_to_see_doctor": "高热不退超过3天、呼吸困难、症状持续加重、合并基础疾病者。",
        "severity": "轻",
    },
    {
        "disease": "流行性感冒",
        "symptoms": ["发热", "乏力", "肌肉酸痛", "头痛", "咳嗽", "咽痛", "寒战"],
        "description": "由流感病毒引起的急性呼吸道传染病，传染性强，症状比普通感冒重。",
        "treatment": "发病48小时内使用奥司他韦等抗病毒药物效果最佳；对症退热、充分休息。",
        "when_to_see_doctor": "高热持续不退、呼吸困难、胸痛、严重呕吐、症状改善后再次加重。",
        "severity": "中",
    },
    {
        "disease": "急性支气管炎",
        "symptoms": ["咳嗽", "咳痰", "胸闷", "发热", "乏力", "气短"],
        "description": "支气管黏膜的急性炎症，常由病毒感染引起，也可继发细菌感染。",
        "treatment": "止咳化痰药、多饮水、保持空气湿润。细菌感染时可使用抗生素。",
        "when_to_see_doctor": "咳血、高热超过3天、呼吸困难、症状超过3周未缓解。",
        "severity": "轻-中",
    },
    {
        "disease": "肺炎",
        "symptoms": ["发热", "咳嗽", "咳痰", "呼吸困难", "胸痛", "乏力", "气短"],
        "description": "肺实质的炎症，可由细菌、病毒、支原体等引起，老年人和免疫力低下者风险更高。",
        "treatment": "细菌性肺炎需抗生素治疗；病毒性肺炎以对症支持治疗为主；重症需住院。",
        "when_to_see_doctor": "出现呼吸困难、高热不退、胸痛、精神状态差应立即就医。",
        "severity": "中-重",
    },
    {
        "disease": "支气管哮喘",
        "symptoms": ["呼吸困难", "气短", "咳嗽", "胸闷", "喘息"],
        "description": "慢性气道炎症性疾病，表现为反复发作的喘息、气促、胸闷和咳嗽。",
        "treatment": "长期控制：吸入糖皮质激素（如布地奈德）；急性发作：速效支气管扩张剂（如沙丁胺醇）。",
        "when_to_see_doctor": "急性发作用药后不缓解、说话困难、口唇发紫、嗜睡。",
        "severity": "中",
    },
    {
        "disease": "高血压",
        "symptoms": ["头痛", "头晕", "心悸", "耳鸣", "乏力", "视力模糊"],
        "description": "以动脉血压持续升高为主要表现的慢性疾病，是心脑血管疾病的主要危险因素。",
        "treatment": "生活方式干预（低盐饮食、运动、戒烟限酒）；降压药物（CCB、ACEI、ARB等）需长期服用。",
        "when_to_see_doctor": "血压突然升高超过180/120mmHg、剧烈头痛、胸痛、意识障碍。",
        "severity": "中",
    },
    {
        "disease": "冠心病",
        "symptoms": ["胸闷", "胸痛", "心悸", "气短", "乏力"],
        "description": "冠状动脉粥样硬化导致血管狭窄或阻塞，引起心肌缺血缺氧的心脏病。",
        "treatment": "抗血小板药物（阿司匹林）、他汀类药物、硝酸甘油缓解心绞痛。严重者需支架或搭桥手术。",
        "when_to_see_doctor": "突发剧烈胸痛超过15分钟不缓解、大汗淋漓、濒死感，立即拨打120。",
        "severity": "重",
    },
    {
        "disease": "心律失常",
        "symptoms": ["心悸", "胸闷", "头晕", "乏力", "气短"],
        "description": "心脏电传导系统异常导致心跳过快、过慢或不规则。",
        "treatment": "根据类型选择：抗心律失常药物、射频消融术、起搏器植入等。",
        "when_to_see_doctor": "持续心悸伴头晕、晕厥、胸痛、呼吸困难。",
        "severity": "中-重",
    },
    {
        "disease": "急性胃肠炎",
        "symptoms": ["腹痛", "腹泻", "恶心", "呕吐", "发热", "乏力"],
        "description": "胃肠道黏膜的急性炎症，多由不洁饮食、病毒或细菌感染引起。",
        "treatment": "补液防脱水（口服补液盐）、清淡饮食、止吐止泻药。细菌感染可用抗生素。",
        "when_to_see_doctor": "严重脱水（尿少、口干、眼窝凹陷）、血便、高热不退、持续呕吐无法进食。",
        "severity": "轻-中",
    },
    {
        "disease": "胃溃疡",
        "symptoms": ["腹痛", "胃胀", "恶心", "食欲不振", "呕吐"],
        "description": "胃黏膜被胃酸和胃蛋白酶消化形成的溃疡，与幽门螺杆菌感染和NSAIDs使用相关。",
        "treatment": "质子泵抑制剂（奥美拉唑）+ 幽门螺杆菌根除治疗（三联/四联疗法）；避免辛辣刺激食物。",
        "when_to_see_doctor": "呕血、黑便、剧烈腹痛突然加重（可能穿孔）、体重明显下降。",
        "severity": "中",
    },
    {
        "disease": "胆囊炎",
        "symptoms": ["腹痛", "恶心", "呕吐", "发热", "食欲不振"],
        "description": "胆囊的炎症，多由胆结石引起，进食油腻食物后右上腹疼痛加重。",
        "treatment": "抗感染、解痉止痛、禁食。反复发作或合并胆结石建议胆囊切除术。",
        "when_to_see_doctor": "持续剧烈右上腹痛、高热寒战、黄疸（皮肤眼睛发黄）。",
        "severity": "中",
    },
    {
        "disease": "泌尿系统感染",
        "symptoms": ["尿频", "尿急", "尿痛", "发热", "腰痛"],
        "description": "细菌侵入泌尿系统引起的感染，女性更常见。上尿路感染（肾盂肾炎）症状更重。",
        "treatment": "多饮水、抗生素治疗（根据尿培养药敏选择）。肾盂肾炎可能需要静脉抗生素。",
        "when_to_see_doctor": "高热寒战、腰痛加重、血尿、恶心呕吐无法进食。",
        "severity": "轻-中",
    },
    {
        "disease": "糖尿病",
        "symptoms": ["多饮", "多尿", "体重变化", "乏力", "视力模糊", "食欲不振"],
        "description": "以血糖升高为特征的代谢性疾病。1型为胰岛素缺乏，2型为胰岛素抵抗为主。",
        "treatment": "饮食控制、运动、口服降糖药（二甲双胍等）或胰岛素注射。定期监测血糖。",
        "when_to_see_doctor": "血糖持续过高、出现酮症酸中毒症状（恶心呕吐、呼吸深快、意识模糊）。",
        "severity": "中",
    },
    {
        "disease": "甲状腺功能亢进",
        "symptoms": ["心悸", "体重变化", "乏力", "失眠", "手抖", "多汗", "食欲不振"],
        "description": "甲状腺激素分泌过多引起的代谢亢进综合征，Graves病最常见。",
        "treatment": "抗甲状腺药物（甲巯咪唑、丙硫氧嘧啶）、放射性碘治疗或手术。",
        "when_to_see_doctor": "心悸加重、高热、烦躁不安、恶心呕吐（甲亢危象前兆）。",
        "severity": "中",
    },
    {
        "disease": "贫血",
        "symptoms": ["乏力", "头晕", "心悸", "气短", "面色苍白", "失眠"],
        "description": "血液中红细胞或血红蛋白低于正常值，缺铁性贫血最常见。",
        "treatment": "缺铁性贫血补充铁剂+维生素C；巨幼细胞贫血补充叶酸/维生素B12；严重贫血需输血。",
        "when_to_see_doctor": "严重头晕、晕厥、心悸气短加重、黑便或血便（提示消化道出血）。",
        "severity": "轻-中",
    },
    {
        "disease": "颈椎病",
        "symptoms": ["头痛", "头晕", "颈肩痛", "手脚麻木", "肌肉酸痛"],
        "description": "颈椎退行性病变压迫神经根、脊髓或椎动脉引起的综合征，与长期低头工作相关。",
        "treatment": "物理治疗、颈托保护、消炎止痛药。严重神经压迫需手术治疗。",
        "when_to_see_doctor": "四肢无力、行走不稳、大小便功能障碍（脊髓压迫征象）。",
        "severity": "轻-中",
    },
    {
        "disease": "腰椎间盘突出",
        "symptoms": ["腰痛", "肌肉酸痛", "手脚麻木", "关节痛"],
        "description": "腰椎间盘纤维环破裂，髓核突出压迫神经根，引起腰痛和下肢放射痛。",
        "treatment": "卧床休息、消炎镇痛药、物理治疗、腰围保护。保守治疗无效或有马尾综合征需手术。",
        "when_to_see_doctor": "下肢无力加重、大小便功能障碍、疼痛严重影响生活。",
        "severity": "中",
    },
    {
        "disease": "关节炎",
        "symptoms": ["关节痛", "肿胀", "肌肉酸痛", "乏力"],
        "description": "关节的炎症性疾病，包括骨关节炎（退行性）和类风湿关节炎（自身免疫性）。",
        "treatment": "骨关节炎：消炎止痛药、关节保护、适当运动。类风湿：免疫抑制剂、生物制剂。",
        "when_to_see_doctor": "关节红肿热痛加重、多个关节同时受累、晨僵超过30分钟。",
        "severity": "中",
    },
    {
        "disease": "焦虑症",
        "symptoms": ["失眠", "心悸", "胸闷", "头晕", "乏力", "食欲不振"],
        "description": "以过度担忧和焦虑为主要特征的精神障碍，可伴多种躯体症状。",
        "treatment": "心理治疗（认知行为治疗）；药物治疗（SSRIs、苯二氮卓类短期使用）。",
        "when_to_see_doctor": "焦虑严重影响工作生活、出现自伤想法、惊恐发作频繁。",
        "severity": "中",
    },
    {
        "disease": "抑郁症",
        "symptoms": ["失眠", "乏力", "食欲不振", "体重变化", "头晕"],
        "description": "以持续情绪低落、兴趣减退为核心症状的精神障碍，常伴躯体症状。",
        "treatment": "抗抑郁药物（SSRIs如舍曲林、氟西汀）+ 心理治疗。需坚持服药至少6-12个月。",
        "when_to_see_doctor": "出现自伤或自杀想法、严重失眠无法正常生活、拒绝进食。",
        "severity": "中-重",
    },
    {
        "disease": "荨麻疹",
        "symptoms": ["皮疹", "瘙痒", "红肿"],
        "description": "皮肤黏膜小血管扩张及通透性增加出现的局限性水肿反应，常由过敏引起。",
        "treatment": "回避过敏原、抗组胺药（氯雷他定、西替利嗪）。严重者使用糖皮质激素。",
        "when_to_see_doctor": "伴呼吸困难或喉头水肿（过敏性休克前兆）、皮疹持续超过6周。",
        "severity": "轻-中",
    },
    {
        "disease": "湿疹",
        "symptoms": ["皮疹", "瘙痒", "红肿", "脱皮"],
        "description": "由多种因素引起的一种具有渗出倾向的皮肤炎症性疾病，反复发作。",
        "treatment": "保湿润肤、外用糖皮质激素软膏、避免刺激因素。严重者口服抗组胺药。",
        "when_to_see_doctor": "皮损面积大、渗出明显、继发感染（红肿热痛加重）。",
        "severity": "轻",
    },
    {
        "disease": "过敏性鼻炎",
        "symptoms": ["鼻塞", "流涕", "打喷嚏", "头痛"],
        "description": "接触过敏原后发生的鼻黏膜非感染性炎症，常见过敏原为花粉、尘螨。",
        "treatment": "回避过敏原、鼻用糖皮质激素喷剂（布地奈德）、抗组胺药。可考虑脱敏治疗。",
        "when_to_see_doctor": "药物控制不佳、合并哮喘症状、鼻窦炎反复发作。",
        "severity": "轻",
    },
    {
        "disease": "偏头痛",
        "symptoms": ["头痛", "恶心", "呕吐", "视力模糊"],
        "description": "反复发作的单侧搏动性头痛，常伴恶心、畏光、畏声，可有先兆症状。",
        "treatment": "急性发作：曲坦类药物、NSAIDs。预防：β受体阻滞剂、抗癫痫药、CGRP单抗。",
        "when_to_see_doctor": "突发剧烈头痛（雷击样）、头痛伴发热和颈强直、进行性加重的头痛。",
        "severity": "中",
    },
    {
        "disease": "中暑",
        "symptoms": ["发热", "头晕", "乏力", "恶心", "头痛", "肌肉酸痛"],
        "description": "在高温环境下体温调节功能障碍引起的急性疾病，严重者可危及生命。",
        "treatment": "立即转移到阴凉处、物理降温（冰敷、喷水扇风）、补充水分和电解质。重症需急救。",
        "when_to_see_doctor": "体温超过40°C、意识障碍、抽搐、无汗，立即拨打120。",
        "severity": "中-重",
    },
]


def search_by_symptoms(symptoms: list[str]) -> list[dict]:
    """基于症状交集匹配疾病，按匹配度排序返回"""
    if not symptoms:
        return []

    results = []
    symptom_set = set(s.strip() for s in symptoms if s.strip())

    for entry in DISEASE_KNOWLEDGE:
        disease_symptoms = set(entry["symptoms"])
        matched = symptom_set & disease_symptoms
        if not matched:
            continue
        score = len(matched) / len(disease_symptoms)
        results.append({
            "disease": entry["disease"],
            "matched_symptoms": list(matched),
            "match_score": round(score, 2),
            "description": entry["description"],
            "treatment": entry["treatment"],
            "when_to_see_doctor": entry["when_to_see_doctor"],
            "severity": entry["severity"],
        })

    results.sort(key=lambda x: (-x["match_score"], -len(x["matched_symptoms"])))
    return results[:5]


def search_by_disease(disease_name: str) -> dict | None:
    """按疾病名精确查找详情"""
    for entry in DISEASE_KNOWLEDGE:
        if entry["disease"] == disease_name or disease_name in entry["disease"]:
            return entry
    return None
