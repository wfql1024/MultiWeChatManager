package com.jfmultichat.core.task;

import jdk.jfr.Event;
import jdk.jfr.Label;
import jdk.jfr.Name;

/**
 * JFR 事件：一个任务跑完记一次（2026-10-12 用户要求"开发中请用上 JFR"）.
 *
 * <p>JFR = JDK 自带的飞行记录器，**零依赖、无录制时开销可忽略**（{@link #commit()} 在没有录制时几乎立即返回，
 * 所以可以无条件调用，不需要开关）。它专门回答"**到底卡在哪**"这类问题：
 * <ul>
 *   <li>只看任务：本事件（类型 / 平台 / 结果 / 耗时 / 最后阶段）</li>
 *   <li>看锁与阻塞：{@code jdk.JavaMonitorEnter}、{@code jdk.ThreadPark}、{@code jdk.SocketRead}…</li>
 * </ul>
 *
 * <p>用法（排查时）：启动加 {@code -XX:StartFlightRecording=filename=app.jfr,duration=10m}，
 * 事后用 {@code jfr print --events com.jfmultichat.TaskRun app.jfr} 或 JMC 看。
 */
@Name("com.jfmultichat.TaskRun")
@Label("任务执行")
public class TaskJfrEvent extends Event {

    @Label("任务类型")
    public String kind;

    @Label("平台")
    public String sw;

    @Label("结果")
    public String result;

    @Label("耗时(毫秒)")
    public long durationMs;

    @Label("最后阶段")
    public String lastPhase;
}
