"""JLPT N5 grammar seed data — 40+ grammar points with examples."""

import logging

from app.database.connection import get_db

logger = logging.getLogger("life-master.grammar-seed")

# (grammar_point, meaning_ko, meaning_en, jlpt_level, category, formation, notes, order_index)
# Each grammar point followed by its examples: (sentence_jp, sentence_ko, sentence_en)

N5_GRAMMAR = [
    # ═══ 조사 (Particles) ═══
    {
        "point": "～は", "ko": "~은/는 (주제)", "en": "topic marker",
        "level": "N5", "cat": "조사", "formation": "명사 + は",
        "notes": "문장의 주제를 나타냄. が와 구분 중요",
        "order": 1,
        "examples": [
            ("私は学生です。", "나는 학생입니다.", "I am a student."),
            ("今日は暑いですね。", "오늘은 덥네요.", "It's hot today, isn't it?"),
            ("これは本です。", "이것은 책입니다.", "This is a book."),
        ],
    },
    {
        "point": "～が", "ko": "~이/가 (주어)", "en": "subject marker",
        "level": "N5", "cat": "조사", "formation": "명사 + が",
        "notes": "주어를 나타냄. 새로운 정보를 도입할 때 사용",
        "order": 2,
        "examples": [
            ("猫がいます。", "고양이가 있습니다.", "There is a cat."),
            ("誰が来ましたか。", "누가 왔습니까?", "Who came?"),
            ("日本語が好きです。", "일본어를 좋아합니다.", "I like Japanese."),
        ],
    },
    {
        "point": "～を", "ko": "~을/를 (목적어)", "en": "object marker",
        "level": "N5", "cat": "조사", "formation": "명사 + を",
        "notes": "타동사의 목적어를 나타냄",
        "order": 3,
        "examples": [
            ("水を飲みます。", "물을 마십니다.", "I drink water."),
            ("本を読みます。", "책을 읽습니다.", "I read a book."),
            ("映画を見ます。", "영화를 봅니다.", "I watch a movie."),
        ],
    },
    {
        "point": "～に", "ko": "~에/에게 (방향/시간/대상)", "en": "direction/time/target",
        "level": "N5", "cat": "조사", "formation": "명사 + に",
        "notes": "장소(존재), 시간, 대상, 방향 등 다양한 용법",
        "order": 4,
        "examples": [
            ("学校に行きます。", "학교에 갑니다.", "I go to school."),
            ("七時に起きます。", "7시에 일어납니다.", "I wake up at 7."),
            ("友達に手紙を書きます。", "친구에게 편지를 씁니다.", "I write a letter to a friend."),
        ],
    },
    {
        "point": "～で", "ko": "~에서/~(으)로 (장소/수단)", "en": "at/by means of",
        "level": "N5", "cat": "조사", "formation": "명사 + で",
        "notes": "행동의 장소, 수단/방법, 재료를 나타냄",
        "order": 5,
        "examples": [
            ("図書館で勉強します。", "도서관에서 공부합니다.", "I study at the library."),
            ("バスで行きます。", "버스로 갑니다.", "I go by bus."),
            ("日本語で話してください。", "일본어로 말해주세요.", "Please speak in Japanese."),
        ],
    },
    {
        "point": "～へ", "ko": "~(으)로 (방향)", "en": "toward",
        "level": "N5", "cat": "조사", "formation": "명사 + へ",
        "notes": "이동의 방향을 나타냄. に와 비슷하지만 방향 강조",
        "order": 6,
        "examples": [
            ("日本へ行きたいです。", "일본으로 가고 싶습니다.", "I want to go to Japan."),
            ("東京へ出張します。", "도쿄로 출장 갑니다.", "I go on a business trip to Tokyo."),
        ],
    },
    {
        "point": "～と", "ko": "~와/과 (동반/인용)", "en": "with/and/quotation",
        "level": "N5", "cat": "조사", "formation": "명사 + と",
        "notes": "동반(~와 함께), 나열(A와 B), 인용(~라고)",
        "order": 7,
        "examples": [
            ("友達と映画を見ます。", "친구와 영화를 봅니다.", "I watch a movie with a friend."),
            ("パンと牛乳を買います。", "빵과 우유를 삽니다.", "I buy bread and milk."),
        ],
    },
    {
        "point": "～も", "ko": "~도", "en": "also/too",
        "level": "N5", "cat": "조사", "formation": "명사 + も",
        "notes": "は/が/を 대신 사용하여 '~도'의 의미",
        "order": 8,
        "examples": [
            ("私も行きます。", "나도 갑니다.", "I'll go too."),
            ("これも美味しいです。", "이것도 맛있습니다.", "This is also delicious."),
        ],
    },
    {
        "point": "～から～まで", "ko": "~부터 ~까지", "en": "from ~ to ~",
        "level": "N5", "cat": "조사", "formation": "명사 + から + 명사 + まで",
        "notes": "시간/장소의 시작과 끝을 나타냄. 각각 단독 사용 가능",
        "order": 9,
        "examples": [
            ("九時から五時まで働きます。", "9시부터 5시까지 일합니다.", "I work from 9 to 5."),
            ("東京から大阪まで新幹線で行きます。", "도쿄에서 오사카까지 신칸센으로 갑니다.", "I go from Tokyo to Osaka by Shinkansen."),
        ],
    },
    {
        "point": "～の", "ko": "~의 (소유/설명)", "en": "possessive/descriptive",
        "level": "N5", "cat": "조사", "formation": "명사 + の + 명사",
        "notes": "소유, 소속, 설명 관계를 나타냄",
        "order": 10,
        "examples": [
            ("私の本です。", "나의 책입니다.", "It's my book."),
            ("日本語の先生です。", "일본어 선생님입니다.", "He/she is a Japanese teacher."),
            ("東京の天気はどうですか。", "도쿄의 날씨는 어떻습니까?", "How is the weather in Tokyo?"),
        ],
    },
    {
        "point": "～や", "ko": "~이나/~와 (예시 나열)", "en": "and (non-exhaustive list)",
        "level": "N5", "cat": "조사", "formation": "명사 + や + 명사 (+ など)",
        "notes": "と와 달리 전부가 아닌 일부를 예시로 나열",
        "order": 11,
        "examples": [
            ("りんごやみかんを買いました。", "사과나 귤을 샀습니다.", "I bought apples, oranges, etc."),
            ("本や雑誌を読みます。", "책이나 잡지를 읽습니다.", "I read books, magazines, etc."),
        ],
    },
    {
        "point": "～か", "ko": "~인가 (의문)", "en": "question marker",
        "level": "N5", "cat": "조사", "formation": "문장 + か",
        "notes": "의문문을 만듦. 선택의문에도 사용",
        "order": 12,
        "examples": [
            ("これは何ですか。", "이것은 무엇입니까?", "What is this?"),
            ("コーヒーか紅茶、どちらがいいですか。", "커피와 홍차, 어느 쪽이 좋습니까?", "Which do you prefer, coffee or tea?"),
        ],
    },
    {
        "point": "～ね", "ko": "~네/~죠 (동의 구함)", "en": "isn't it / right?",
        "level": "N5", "cat": "조사", "formation": "문장 + ね",
        "notes": "상대방의 동의를 구하거나 확인할 때",
        "order": 13,
        "examples": [
            ("いい天気ですね。", "좋은 날씨네요.", "Nice weather, isn't it?"),
            ("この料理は美味しいですね。", "이 요리는 맛있네요.", "This food is delicious, isn't it?"),
        ],
    },
    {
        "point": "～よ", "ko": "~요 (강조/알림)", "en": "emphasis/informing",
        "level": "N5", "cat": "조사", "formation": "문장 + よ",
        "notes": "상대방에게 새로운 정보를 알릴 때, 주장/강조",
        "order": 14,
        "examples": [
            ("これは美味しいですよ。", "이거 맛있어요.", "This is delicious, you know!"),
            ("明日は休みですよ。", "내일은 쉬는 날이에요.", "Tomorrow is a day off!"),
        ],
    },
    # ═══ 동사활용 (Verb conjugation) ═══
    {
        "point": "～ます形", "ko": "정중형 (ます)", "en": "polite form (masu)",
        "level": "N5", "cat": "동사활용", "formation": "동사 어간 + ます",
        "notes": "정중한 현재/미래 긍정형. ません=부정, ました=과거",
        "order": 15,
        "examples": [
            ("毎日日本語を勉強します。", "매일 일본어를 공부합니다.", "I study Japanese every day."),
            ("昨日テレビを見ませんでした。", "어제 텔레비전을 보지 않았습니다.", "I didn't watch TV yesterday."),
        ],
    },
    {
        "point": "～て形", "ko": "て형 (연결/요청)", "en": "te-form (connecting/request)",
        "level": "N5", "cat": "동사활용", "formation": "동사 て형 변환 (5단/1단/불규칙)",
        "notes": "동작의 연결, 요청(~てください), 진행(~ている) 등에 사용",
        "order": 16,
        "examples": [
            ("朝ごはんを食べて、学校に行きます。", "아침밥을 먹고 학교에 갑니다.", "I eat breakfast and go to school."),
            ("ここに座ってください。", "여기에 앉아주세요.", "Please sit here."),
            ("今、本を読んでいます。", "지금 책을 읽고 있습니다.", "I'm reading a book now."),
        ],
    },
    {
        "point": "～ない形", "ko": "부정형 (ない)", "en": "negative form (nai)",
        "level": "N5", "cat": "동사활용", "formation": "동사 あ단 + ない (5단), 어간 + ない (1단)",
        "notes": "동사의 보통체 부정형. する→しない, 来る→来ない",
        "order": 17,
        "examples": [
            ("肉を食べない。", "고기를 먹지 않는다.", "I don't eat meat."),
            ("明日は学校に行かない。", "내일은 학교에 가지 않는다.", "I won't go to school tomorrow."),
        ],
    },
    {
        "point": "～た形", "ko": "과거형 (た)", "en": "past form (ta)",
        "level": "N5", "cat": "동사활용", "formation": "て형과 동일 변환 후 て→た, で→だ",
        "notes": "보통체 과거형. 경험(~たことがある)에도 활용",
        "order": 18,
        "examples": [
            ("昨日映画を見た。", "어제 영화를 봤다.", "I watched a movie yesterday."),
            ("もう宿題をした。", "이미 숙제를 했다.", "I already did my homework."),
        ],
    },
    {
        "point": "～辞書形", "ko": "사전형 (기본형)", "en": "dictionary form",
        "level": "N5", "cat": "동사활용", "formation": "동사의 기본형 (사전에 실린 형태)",
        "notes": "보통체, 명사 수식, ~ことができる 등에 사용",
        "order": 19,
        "examples": [
            ("日本語を話すことができます。", "일본어를 말할 수 있습니다.", "I can speak Japanese."),
            ("毎朝走る。", "매일 아침 달린다.", "I run every morning."),
        ],
    },
    # ═══ 문형 (Sentence patterns) ═══
    {
        "point": "～たい", "ko": "~하고 싶다", "en": "want to ~",
        "level": "N5", "cat": "문형", "formation": "동사 ます형 어간 + たい",
        "notes": "자신의 희망을 나타냄. 3인칭에는 ~たがる 사용",
        "order": 20,
        "examples": [
            ("日本に行きたいです。", "일본에 가고 싶습니다.", "I want to go to Japan."),
            ("冷たいものが飲みたい。", "차가운 것이 마시고 싶다.", "I want to drink something cold."),
        ],
    },
    {
        "point": "～ましょう", "ko": "~합시다 (제안/권유)", "en": "let's ~",
        "level": "N5", "cat": "문형", "formation": "동사 ます형 어간 + ましょう",
        "notes": "제안, 권유, 자발적 의지 표현",
        "order": 21,
        "examples": [
            ("一緒に昼ごはんを食べましょう。", "같이 점심을 먹읍시다.", "Let's eat lunch together."),
            ("始めましょう。", "시작합시다.", "Let's begin."),
        ],
    },
    {
        "point": "～てください", "ko": "~해주세요 (요청)", "en": "please do ~",
        "level": "N5", "cat": "문형", "formation": "동사 て형 + ください",
        "notes": "정중한 요청/부탁",
        "order": 22,
        "examples": [
            ("もう一度言ってください。", "한 번 더 말해주세요.", "Please say it once more."),
            ("名前を書いてください。", "이름을 써주세요.", "Please write your name."),
            ("窓を開けてください。", "창문을 열어주세요.", "Please open the window."),
        ],
    },
    {
        "point": "～てもいい", "ko": "~해도 된다 (허가)", "en": "may / it's okay to ~",
        "level": "N5", "cat": "문형", "formation": "동사 て형 + もいい(ですか)",
        "notes": "허가를 구하거나 부여할 때",
        "order": 23,
        "examples": [
            ("ここに座ってもいいですか。", "여기에 앉아도 됩니까?", "May I sit here?"),
            ("写真を撮ってもいいですよ。", "사진을 찍어도 됩니다.", "You may take pictures."),
        ],
    },
    {
        "point": "～てはいけない", "ko": "~하면 안 된다 (금지)", "en": "must not ~",
        "level": "N5", "cat": "문형", "formation": "동사 て형 + はいけない/はいけません",
        "notes": "금지를 나타냄",
        "order": 24,
        "examples": [
            ("ここでたばこを吸ってはいけません。", "여기서 담배를 피우면 안 됩니다.", "You must not smoke here."),
            ("試験中に話してはいけない。", "시험 중에 말하면 안 된다.", "You must not talk during the exam."),
        ],
    },
    {
        "point": "～なければならない", "ko": "~하지 않으면 안 된다 (의무)", "en": "must / have to ~",
        "level": "N5", "cat": "문형", "formation": "동사 ない형 (ない→なければ) + ならない",
        "notes": "의무, 필요를 나타냄. ~なきゃ(구어)로도 사용",
        "order": 25,
        "examples": [
            ("毎日勉強しなければなりません。", "매일 공부하지 않으면 안 됩니다.", "I have to study every day."),
            ("薬を飲まなければならない。", "약을 먹지 않으면 안 된다.", "I have to take medicine."),
        ],
    },
    {
        "point": "～ことができる", "ko": "~할 수 있다 (가능)", "en": "can / be able to ~",
        "level": "N5", "cat": "문형", "formation": "동사 사전형 + ことができる",
        "notes": "능력이나 가능성을 나타냄",
        "order": 26,
        "examples": [
            ("漢字を読むことができます。", "한자를 읽을 수 있습니다.", "I can read kanji."),
            ("自転車に乗ることができますか。", "자전거를 탈 수 있습니까?", "Can you ride a bicycle?"),
        ],
    },
    {
        "point": "～たことがある", "ko": "~한 적이 있다 (경험)", "en": "have done ~ (experience)",
        "level": "N5", "cat": "문형", "formation": "동사 た형 + ことがある",
        "notes": "과거의 경험을 나타냄",
        "order": 27,
        "examples": [
            ("日本に行ったことがあります。", "일본에 간 적이 있습니다.", "I have been to Japan."),
            ("寿司を食べたことがありますか。", "초밥을 먹어본 적이 있습니까?", "Have you ever eaten sushi?"),
        ],
    },
    {
        "point": "～つもり", "ko": "~할 생각이다 (의도)", "en": "intend to ~",
        "level": "N5", "cat": "문형", "formation": "동사 사전형 + つもり(だ/です)",
        "notes": "의도, 계획을 나타냄",
        "order": 28,
        "examples": [
            ("来年日本に行くつもりです。", "내년에 일본에 갈 생각입니다.", "I intend to go to Japan next year."),
            ("大学で日本語を勉強するつもりだ。", "대학에서 일본어를 공부할 생각이다.", "I plan to study Japanese at university."),
        ],
    },
    {
        "point": "～予定", "ko": "~할 예정이다", "en": "be scheduled to ~",
        "level": "N5", "cat": "문형", "formation": "동사 사전형 + 予定(だ/です)",
        "notes": "확정된 계획, 일정을 나타냄",
        "order": 29,
        "examples": [
            ("来月結婚する予定です。", "다음 달 결혼할 예정입니다.", "I'm scheduled to get married next month."),
            ("三時に会議がある予定です。", "3시에 회의가 있을 예정입니다.", "There's a meeting scheduled at 3."),
        ],
    },
    {
        "point": "～と思う", "ko": "~라고 생각하다", "en": "I think ~",
        "level": "N5", "cat": "문형", "formation": "보통형 + と思う/と思います",
        "notes": "자신의 의견, 추측을 나타냄",
        "order": 30,
        "examples": [
            ("明日は雨だと思います。", "내일은 비라고 생각합니다.", "I think it will rain tomorrow."),
            ("この映画は面白いと思う。", "이 영화는 재미있다고 생각한다.", "I think this movie is interesting."),
        ],
    },
    {
        "point": "～でしょう", "ko": "~이겠지요 (추측)", "en": "probably / I suppose",
        "level": "N5", "cat": "문형", "formation": "보통형 + でしょう",
        "notes": "추측, 완곡한 판단을 나타냄",
        "order": 31,
        "examples": [
            ("明日はいい天気でしょう。", "내일은 좋은 날씨겠지요.", "It will probably be nice weather tomorrow."),
            ("彼は来ないでしょう。", "그는 오지 않겠지요.", "He probably won't come."),
        ],
    },
    {
        "point": "～かもしれない", "ko": "~일지도 모른다 (가능성)", "en": "might / maybe",
        "level": "N5", "cat": "문형", "formation": "보통형 + かもしれない/かもしれません",
        "notes": "불확실한 추측, 가능성을 나타냄",
        "order": 32,
        "examples": [
            ("明日は雪かもしれません。", "내일은 눈일지도 모릅니다.", "It might snow tomorrow."),
            ("彼は忙しいかもしれない。", "그는 바쁠지도 모른다.", "He might be busy."),
        ],
    },
    {
        "point": "～ている", "ko": "~하고 있다 (진행/상태)", "en": "be ~ing / state",
        "level": "N5", "cat": "문형", "formation": "동사 て형 + いる/います",
        "notes": "진행 중인 동작 또는 결과 상태를 나타냄",
        "order": 33,
        "examples": [
            ("今テレビを見ています。", "지금 텔레비전을 보고 있습니다.", "I'm watching TV now."),
            ("東京に住んでいます。", "도쿄에 살고 있습니다.", "I live in Tokyo."),
            ("結婚しています。", "결혼해 있습니다.", "I am married."),
        ],
    },
    {
        "point": "～てから", "ko": "~하고 나서 (순서)", "en": "after doing ~",
        "level": "N5", "cat": "문형", "formation": "동사 て형 + から",
        "notes": "시간적 순서를 명확히 나타냄",
        "order": 34,
        "examples": [
            ("手を洗ってから食べます。", "손을 씻고 나서 먹습니다.", "I eat after washing my hands."),
            ("日本に来てから日本語を勉強しました。", "일본에 온 후 일본어를 공부했습니다.", "I studied Japanese after coming to Japan."),
        ],
    },
    {
        "point": "～ないでください", "ko": "~하지 말아주세요 (금지 요청)", "en": "please don't ~",
        "level": "N5", "cat": "문형", "formation": "동사 ない형 + でください",
        "notes": "정중하게 하지 말 것을 요청",
        "order": 35,
        "examples": [
            ("ここで写真を撮らないでください。", "여기서 사진을 찍지 말아주세요.", "Please don't take pictures here."),
            ("心配しないでください。", "걱정하지 말아주세요.", "Please don't worry."),
        ],
    },
    # ═══ 형용사활용 (Adjective conjugation) ═══
    {
        "point": "い形容詞 + くない", "ko": "い형용사 부정형", "en": "i-adj negative",
        "level": "N5", "cat": "형용사활용", "formation": "い → くない (ex: 高い → 高くない)",
        "notes": "い형용사의 부정. 과거부정: くなかった",
        "order": 36,
        "examples": [
            ("この本は高くないです。", "이 책은 비싸지 않습니다.", "This book is not expensive."),
            ("昨日は暑くなかった。", "어제는 덥지 않았다.", "It wasn't hot yesterday."),
        ],
    },
    {
        "point": "な形容詞 + じゃない", "ko": "な형용사 부정형", "en": "na-adj negative",
        "level": "N5", "cat": "형용사활용", "formation": "な형용사 + じゃない/ではない",
        "notes": "な형용사의 부정. 과거부정: じゃなかった",
        "order": 37,
        "examples": [
            ("この問題は簡単じゃないです。", "이 문제는 간단하지 않습니다.", "This problem is not simple."),
            ("あの人は親切じゃなかった。", "그 사람은 친절하지 않았다.", "That person was not kind."),
        ],
    },
    {
        "point": "い形容詞 + かった", "ko": "い형용사 과거형", "en": "i-adj past",
        "level": "N5", "cat": "형용사활용", "formation": "い → かった (ex: 楽しい → 楽しかった)",
        "notes": "い형용사의 과거형",
        "order": 38,
        "examples": [
            ("昨日の映画は面白かったです。", "어제 영화는 재미있었습니다.", "Yesterday's movie was interesting."),
            ("旅行は楽しかった。", "여행은 즐거웠다.", "The trip was fun."),
        ],
    },
    # ═══ 접속사/기타 (Conjunctions/Others) ═══
    {
        "point": "～が (역접)", "ko": "~지만 (역접 접속)", "en": "but / however",
        "level": "N5", "cat": "접속", "formation": "문장1 + が、+ 문장2",
        "notes": "앞 문장과 반대/대조되는 내용을 연결",
        "order": 39,
        "examples": [
            ("日本語は難しいですが、面白いです。", "일본어는 어렵지만 재미있습니다.", "Japanese is difficult, but interesting."),
            ("行きたいですが、時間がありません。", "가고 싶지만 시간이 없습니다.", "I want to go, but I don't have time."),
        ],
    },
    {
        "point": "～から (이유)", "ko": "~니까/~때문에 (이유)", "en": "because ~",
        "level": "N5", "cat": "접속", "formation": "문장(보통형/정중형) + から",
        "notes": "이유, 원인을 나타냄. 주관적 이유에 주로 사용",
        "order": 40,
        "examples": [
            ("暑いから、窓を開けてください。", "더우니까 창문을 열어주세요.", "Because it's hot, please open the window."),
            ("病気だから、学校を休みます。", "아프니까 학교를 쉽니다.", "Because I'm sick, I'll take a day off."),
        ],
    },
    {
        "point": "～のに", "ko": "~인데도 (불만/의외)", "en": "even though / despite",
        "level": "N5", "cat": "접속", "formation": "보통형 + のに (な형: なのに)",
        "notes": "예상과 다른 결과에 대한 불만/유감",
        "order": 41,
        "examples": [
            ("たくさん食べたのに、まだお腹がすいている。", "많이 먹었는데도 아직 배가 고프다.", "Even though I ate a lot, I'm still hungry."),
            ("約束したのに、来なかった。", "약속했는데 오지 않았다.", "Even though we promised, he didn't come."),
        ],
    },
    {
        "point": "～とき", "ko": "~할 때 (시간)", "en": "when ~",
        "level": "N5", "cat": "문형", "formation": "동사 보통형/명사の/な형な/い형 + とき",
        "notes": "어떤 동작이나 상태의 시점을 나타냄",
        "order": 42,
        "examples": [
            ("日本にいたとき、毎日寿司を食べました。", "일본에 있었을 때 매일 초밥을 먹었습니다.", "When I was in Japan, I ate sushi every day."),
            ("暇なとき、映画を見ます。", "한가할 때 영화를 봅니다.", "When I'm free, I watch movies."),
        ],
    },
    {
        "point": "～前に", "ko": "~하기 전에", "en": "before ~",
        "level": "N5", "cat": "문형", "formation": "동사 사전형 + 前に / 명사の + 前に",
        "notes": "시간적으로 앞선 시점을 나타냄",
        "order": 43,
        "examples": [
            ("寝る前に歯を磨きます。", "자기 전에 이를 닦습니다.", "I brush my teeth before going to bed."),
            ("食事の前に手を洗ってください。", "식사 전에 손을 씻어주세요.", "Please wash your hands before the meal."),
        ],
    },
    {
        "point": "～後で", "ko": "~한 후에", "en": "after ~",
        "level": "N5", "cat": "문형", "formation": "동사 た형 + 後で / 명사の + 後で",
        "notes": "시간적으로 뒤의 시점을 나타냄",
        "order": 44,
        "examples": [
            ("昼ごはんを食べた後で、散歩します。", "점심을 먹은 후에 산책합니다.", "After eating lunch, I take a walk."),
            ("授業の後で図書館に行きます。", "수업 후에 도서관에 갑니다.", "I go to the library after class."),
        ],
    },
]


async def seed_grammar_data() -> int:
    """Seed N5 grammar points and examples into the database."""
    db = await get_db()
    count = 0

    for g in N5_GRAMMAR:
        # Check if already exists
        cursor = await db.execute(
            "SELECT id FROM jp_grammar WHERE grammar_point = ? AND jlpt_level = ?",
            (g["point"], g["level"]),
        )
        existing = await cursor.fetchone()
        if existing:
            continue

        # Insert grammar point
        await db.execute(
            """INSERT INTO jp_grammar
               (grammar_point, meaning_ko, meaning_en, jlpt_level, category, formation, notes, order_index)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (g["point"], g["ko"], g["en"], g["level"], g["cat"],
             g["formation"], g["notes"], g["order"]),
        )
        cursor = await db.execute("SELECT last_insert_rowid()")
        grammar_id = (await cursor.fetchone())[0]

        # Insert examples
        for ex in g["examples"]:
            await db.execute(
                """INSERT INTO jp_grammar_example
                   (grammar_id, sentence_jp, sentence_ko, sentence_en)
                   VALUES (?, ?, ?, ?)""",
                (grammar_id, ex[0], ex[1], ex[2]),
            )

        # Create SRS card
        await db.execute(
            "INSERT INTO jp_grammar_srs (grammar_id) VALUES (?)",
            (grammar_id,),
        )

        count += 1

    await db.commit()
    logger.info("Seeded %d N5 grammar points", count)
    return count
