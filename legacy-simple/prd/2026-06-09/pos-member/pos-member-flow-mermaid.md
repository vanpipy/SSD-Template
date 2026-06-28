```mermaid
flowchart TD
    Start(["收银会话开始"]) --> HomeMember{"首页会员栏<br>是否已登录?"}

    %% ── 路径A：会员未登录 → 去登录 ──
    HomeMember -->|"未登录·去登录"| LoginPage["会员登录页"]

    LoginPage --> LoginMethod{"识别方式?"}
    LoginMethod -->|"手机号"| InputPhone["输入会员手机号"]
    LoginMethod -->|"被扫会员码"| ScanCode["PDA扫码识别"]

    InputPhone --> ClickLogin["点击「登录」"]
    ScanCode --> ScanDone{"扫码完成?"}

    ScanDone -->|"超时/无效"| ScanFail["Toast·停留登录页"]
    ScanFail --> LoginMethod

    ScanDone -->|"解析成功"| CheckBind2{"已绑定会员?"}

    ClickLogin --> CheckBind{"已绑定会员?"}

    %% ── 路径D：已绑定 → 解绑弹窗 ──
    CheckBind -->|"已绑定"| UnbindPop["弹窗：「已绑定会员<br>是否解绑并更换？」"]
    CheckBind2 -->|"已绑定"| UnbindPop

    UnbindPop --> UnbindConfirm{"确认解绑?"}
    UnbindConfirm -->|"取消"| HomeLogged
    UnbindConfirm -->|"确认"| ClearOld["清除旧会员"]

    %% ── 路径A/B：未绑定 → 查询接口 ──
    CheckBind -->|"未绑定"| CallLogin["POST /api/member/login"]
    CheckBind2 -->|"未绑定"| CallScan["POST /api/member/scan-login"]

    ClearOld --> CallLogin

    CallLogin --> LoginResult{"查询结果?"}
    CallScan --> ScanResult{"查询结果?"}

    %% ── 成功 ──
    LoginResult -->|"code=0·存在"| StoreMember["存储会员至当前会话"]
    ScanResult -->|"code=0·成功"| StoreMember

    StoreMember --> ToastOK["Toast「会员已登录」"]
    ToastOK --> HomeLogged["首页·会员栏已登录"]

    %% ── 失败 ──
    LoginResult -->|"code=4001·不存在"| PopReg["弹窗：「会员不存在<br>是否立即注册？」"]
    ScanResult -->|"code=4003·无效"| ScanToast["Toast·停留登录页"]
    ScanToast --> LoginMethod

    PopReg --> RegChoice{"选择?"}
    RegChoice -->|"确认注册"| RegPage["会员注册页<br>（预填手机号）"]

    %% ── 路径B：主动注册 ──
    LoginPage -->|"底部·去注册会员"| RegPageEmpty["会员注册页<br>（输入框为空）"]

    RegPageEmpty --> ClickReg["点击「注册」"]
    RegPage --> ClickReg

    %% ── 已绑定检查 ──
    ClickReg --> ChkBind3{"已绑定会员?"}
    ChkBind3 -->|"已绑定"| UnbindPop
    ChkBind3 -->|"未绑定"| CallReg["POST /api/member/register"]

    CallReg --> RegResult{"注册结果?"}
    RegResult -->|"code=0·成功"| StoreMember
    RegResult -->|"code=4002·已注册"| RegFail["Toast「该手机号已注册<br>请直接登录」"]
    RegFail --> LoginPage

    RegChoice -->|"取消"| LoginPage

    %% ── 路径C：会员已登录 → 进入收银 ──
    HomeMember -->|"已登录·进入收银"| AddItems["商品扫码加车"]
    HomeLogged --> AddItems

    AddItems --> Checkout["购物车·结算收款"]

    %% ── 路径D：切换会员 ──
    HomeLogged -->|"点击切换会员"| UnbindPop

    %% ── 路径C：支付即会员 ──
    Checkout --> CheckMember{"订单已绑定会员?"}
    CheckMember -->|"已绑定"| PayNow["直接发起支付扣款"]
    CheckMember -->|"无会员"| ScanPayCode["扫取顾客付款码"]

    ScanPayCode --> PayCenter["支付中心<br>解析付款码·识别渠道"]
    PayCenter --> Channel["银行渠道<br>请求支付宝/微信侧"]
    Channel --> GetId{"获取身份标识?"}
    GetId -->|"成功·alipayuid / openid"| QueryMember["POST /api/member/query-by-payment<br>会员中心查询"]

    QueryMember --> QueryResult{"查询结果?"}
    QueryResult -->|"是会员·code=0"| BindPromo["绑定会员至订单<br>重新促销计算"]
    BindPromo --> ConfirmAmt["店员确认新金额"]
    ConfirmAmt --> PayNow
    QueryResult -->|"非会员·code=4005"| PayNow

    GetId -->|"超时/异常"| PayNow

    PayNow --> PayDone(["支付完成"])

    %% ── 样式 ──
    classDef startEnd fill:#e8f5e9,stroke:#2e7d32,stroke-width:1.5px,color:#1b5e20
    classDef process fill:#e3f2fd,stroke:#1565c0,stroke-width:1px,color:#0d47a1
    classDef decision fill:#fff3e0,stroke:#e65100,stroke-width:1.5px,color:#bf360c
    classDef error fill:#ffebee,stroke:#c62828,stroke-width:1px,color:#b71c1c
    classDef payment fill:#f3e5f5,stroke:#7b1fa2,stroke-width:1.5px,color:#4a148c

    class Start,PayDone startEnd
    class HomeLogged process
    class LoginPage,InputPhone,ScanCode,ClickLogin,ScanDone,StoreMember,ToastOK,ClearOld,CallLogin,CallScan,PopReg,RegPage,RegPageEmpty,ClickReg,CallReg,RegFail,ScanFail,ScanToast,AddItems,Checkout,PayNow,ScanPayCode,PayCenter,Channel,QueryMember,BindPromo,ConfirmAmt process
    class HomeMember,LoginMethod,CheckBind,CheckBind2,UnbindConfirm,LoginResult,ScanResult,RegChoice,ChkBind3,RegResult,CheckMember,GetId,QueryResult decision
    class UnbindPop error
    class ScanPayCode,PayCenter,Channel,QueryMember,BindPromo,ConfirmAmt payment
