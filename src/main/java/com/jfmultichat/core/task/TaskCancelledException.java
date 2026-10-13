package com.jfmultichat.core.task;

/**
 * 任务被取消时抛出的异常（协作式取消的"展开手段"）.
 *
 * <p>为什么用异常而不是"层层 return false"：取消点往往在很深的地方（如等窗口的轮询循环里），
 * 用异常可以**一路弹回任务边界**，只在 {@link TaskRegistry} 里捕获一次 —— 各层业务代码不必写
 * `if (cancelled) return ...`（框架内部也是这么做的：{@code InterruptedException} / {@code CancellationException}）。
 *
 * <p>注意：它**不是**错误，任务中心会把任务标成 {@code CANCELLED}（而不是 {@code FAILED}）。
 */
public class TaskCancelledException extends RuntimeException {
    public TaskCancelledException() {
        super("任务已取消");
    }
}
