plugins {
    id("application")
    id("org.openjfx.javafxplugin") version "0.1.0"
}

group = "com.jfmultichat"
version = "0.1.0"

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
