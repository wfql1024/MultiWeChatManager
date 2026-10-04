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
    applicationDefaultJvmArgs = listOf(
        "--add-exports", "javafx.web/com.sun.javafx.webkit=ALL-UNNAMED"
    )
}

tasks.named<JavaExec>("run") {
    jvmArgs("--add-exports", "javafx.web/com.sun.javafx.webkit=ALL-UNNAMED")
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
