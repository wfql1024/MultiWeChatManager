plugins {
    id("application")
    id("org.openjfx.javafxplugin") version "0.1.0"
}

group = "com.jfmultichat"
version = "4.0.0"

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

tasks.withType<Test> {
    useJUnitPlatform()
    // 测试不经过 Launcher → jfmultichat.logdir 属性为空 → 主 logback.xml 的
    // ${jfmultichat.logdir:-logs} 会回退成**相对路径 logs/**，写进**项目根**
    //（用户 2026-10-11 发现项目根冒出日志，首行是 [Test worker] 就是它）。
    // 这里显式指到 build/test-logs：测试日志永远不会污染项目根；
    // src/test/resources/logback-test.xml 则让测试默认只打控制台、不落盘。
    systemProperty("jfmultichat.logdir",
        layout.buildDirectory.dir("test-logs").get().asFile.absolutePath)
}

tasks.withType<JavaCompile> {
    options.encoding = "UTF-8"
}

javafx {
    version = "17.0.2"
    modules("javafx.controls", "javafx.graphics", "javafx.base", "javafx.web")
}

application {
    mainClass.set("com.jfmultichat.Launcher")
    // sun.awt.shell：取 Windows 原生大图标（32x32）提取 exe 图标用（FileSystemView 只有 16x16，放大后模糊）
    applicationDefaultJvmArgs = listOf(
        "--add-exports", "javafx.web/com.sun.javafx.webkit=ALL-UNNAMED",
        "--add-exports", "java.desktop/sun.awt.shell=ALL-UNNAMED",
        // 控制台/文件编码统一 UTF-8（用户 2026-10-11）：
        //   · file.encoding        → 读写文本文件（配置/JSON）默认 UTF-8
        //   · sun.stdout/stderr.encoding → JDK 17 上 System.out/err 的输出编码（JDK 18+ 改名为 stdout.encoding）
        // 注意：JVM 发 UTF-8 字节只是**一半**，终端也得按 UTF-8 解码，否则一样乱码 ——
        // 终端侧见 AGENTS/DEV_LOGS 里的说明（chcp 65001 或 VS Code 的 UTF-8 终端 profile）。
        "-Dfile.encoding=UTF-8",
        "-Dsun.stdout.encoding=UTF-8",
        "-Dsun.stderr.encoding=UTF-8"
    )
}

tasks.named<JavaExec>("run") {
    jvmArgs("--add-exports", "javafx.web/com.sun.javafx.webkit=ALL-UNNAMED")
    jvmArgs("--add-exports", "java.desktop/sun.awt.shell=ALL-UNNAMED")
    // 中文抗锯齿【试验开关】：JavaFX 默认用 LCD 次像素抗锯齿（实测彩色边缘占比 97%），
    // 深色底 + 中文复杂笔画会显得发虚/带彩边；关掉改用灰度抗锯齿后实测边缘对比度反而更高（53.5 vs 51.3）。
    // 觉得不好就去掉这一行（详见 MEMORY/LESSONS 十四）。
    jvmArgs("-Dprism.lcdtext=false")
    // 控制台编码（同上，gradle run 走这条路径）
    jvmArgs("-Dfile.encoding=UTF-8", "-Dsun.stdout.encoding=UTF-8", "-Dsun.stderr.encoding=UTF-8")
}

// === 开发者工具源集（发布辅助工具，复用 main 的类与依赖，但不进入应用产物） ===
sourceSets {
    create("tools") {
        java.srcDir("src/tools/java")
        compileClasspath += sourceSets["main"].output + configurations["runtimeClasspath"]
        runtimeClasspath += output + compileClasspath
    }
}

/** 加密远程配置：scripts/original_remote_<global|sw>_<vN>.json → remote_configs/ */
tasks.register<JavaExec>("encryptRemoteConfigs") {
    group = "release"
    description = "加密 scripts/original_remote_*.json 并输出到 remote_configs/（复用 CryptoUtils）"
    mainClass.set("com.jfmultichat.tools.EncryptRemoteConfigs")
    classpath = sourceSets["tools"].runtimeClasspath
    workingDir = projectDir
    args(projectDir.absolutePath)
}

/** Python（python 分支）工程目录；默认取同级 MultiWeChatManager，可用 -PpythonRepo=... 覆盖 */
val pythonRepoPath = (findProperty("pythonRepo") as String?) ?: "../MultiWeChatManager"

/** 只做版本适配同步：v2/v10（main）→ v1/v9（python 工程） */
tasks.register<JavaExec>("syncLegacyConfigs") {
    group = "release"
    description = "把本工程 scripts/ 里的现代版 JSON 同步为 Python 工程的旧版 JSON（版本适配中间脚本）"
    mainClass.set("com.jfmultichat.tools.LegacyConfigSync")
    classpath = sourceSets["tools"].runtimeClasspath
    workingDir = projectDir
    args(projectDir.absolutePath, pythonRepoPath)
}

/** 一键发布：加密 main 版 + 同步并加密 python 版 */
tasks.register<JavaExec>("publishRemoteConfigs") {
    group = "release"
    description = "一键发布远程配置：加密 v2/v10 → 同步 v1/v9 → 加密 v1/v9（Python 工程）"
    mainClass.set("com.jfmultichat.tools.PublishRemoteConfigs")
    classpath = sourceSets["tools"].runtimeClasspath
    workingDir = projectDir
    args(projectDir.absolutePath, pythonRepoPath)
}

repositories {
    mavenCentral()
}

dependencies {
    implementation("com.fasterxml.jackson.core:jackson-databind:2.16.1")

    // JNA for Windows API access
    implementation("net.java.dev.jna:jna:5.14.0")
    implementation("net.java.dev.jna:jna-platform:5.14.0")

    // Logging — SLF4J + Logback
    implementation("org.slf4j:slf4j-api:2.0.9")
    implementation("ch.qos.logback:logback-classic:1.4.14")
    implementation("org.slf4j:jul-to-slf4j:2.0.9")

    // Testing — JUnit 5
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}
