package com.jfmultichat;

import javafx.application.Application;

/**
 * 启动入口 — 规避 JavaFX 模块限制.
 * <p>
 * 如果 main class 直接 extends Application，在某些 JDK 上会触发
 * "JavaFX runtime components are missing" 错误。
 * 通过分离启动类来解决。
 */
public class Launcher {
    public static void main(String[] args) {
        Application.launch(MainApp.class, args);
    }
}
