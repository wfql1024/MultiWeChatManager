package com.jfmultichat.config;

/**
 * 应用版本与元信息.
 * 打包程序从此处读取版本号、产品名、公司名等，注入到可执行文件资源中.
 * <p>
 * 对应旧版 {@code .meta/version.txt} (VSVersionInfo).
 */
public final class AppVersion {

    private AppVersion() {}

    /** 当前版本号（四段式: major.minor.patch.build） */
    public static final String VERSION = "4.0.0.7000";

    /** 版本元组 (major, minor, patch, build) */
    public static final int[] VERSION_TUPLE = {4, 0, 0, 7000};

    /** 产品名称 */
    public static final String PRODUCT_NAME = "极峰多聊";

    /** 内部名称 */
    public static final String INTERNAL_NAME = "极峰多聊";

    /** 文件说明 */
    public static final String FILE_DESCRIPTION = "极峰多聊，旨在提升聊天平台多开使用体验。";

    /** 公司名称 */
    public static final String COMPANY_NAME = "极峰创科 JhiFeng Chan Tech Studio";

    /** 版权 */
    public static final String LEGAL_COPYRIGHT = "吾峰起浪 © 版权所有";

    /** 原始文件名 */
    public static final String ORIGINAL_FILENAME = "JhiFengMultiChat.exe";

    /**
     * 将版本字符串解析为可比较的元组.
     * 支持格式: "v3.12.0.6136-Beta", "4.0.0.7000"
     *
     * @return [major, minor, patch, build, suffixRank]
     *         suffixRank: 0=release, 1=Alpha, 2=Beta, 3=RC
     */
    public static int[] parseVersion(String ver) {
        // 去掉前缀 v/V
        String v = ver.trim();
        if (v.startsWith("v") || v.startsWith("V")) v = v.substring(1);

        // 分离后缀
        int suffixRank = 0; // release
        String[] parts = v.split("-", 2);
        String numPart = parts[0].trim();
        if (parts.length > 1) {
            String suffix = parts[1].trim().toLowerCase();
            if (suffix.contains("alpha")) suffixRank = 1;
            else if (suffix.contains("beta")) suffixRank = 2;
            else if (suffix.contains("rc")) suffixRank = 3;
        }

        // 解析数字部分
        String[] nums = numPart.split("\\.");
        int[] result = new int[5];
        for (int i = 0; i < 4; i++) {
            result[i] = i < nums.length ? parseIntSafe(nums[i]) : 0;
        }
        result[4] = suffixRank;
        return result;
    }

    /**
     * 比较两个版本字符串，返回较新的那个.
     * 与 Python file_utils.get_newest_full_version 等效.
     */
    public static String getNewestVersion(String a, String b) {
        int[] va = parseVersion(a);
        int[] vb = parseVersion(b);
        for (int i = 0; i < 5; i++) {
            if (va[i] != vb[i]) return va[i] > vb[i] ? a : b;
        }
        return a; // 相等返回前者
    }

    /**
     * 从本地所有版本中分离高于和低于等于当前版本的列表.
     * 与 Python split_vers_by_cur_from_local 等效.
     *
     * @param currentVer 当前版本
     * @param allVersions 所有版本列表
     * @return [newerVersions, olderOrEqualVersions] 或 null
     */
    public static String[][] splitVersions(String currentVer, java.util.List<String> allVersions) {
        if (allVersions == null || allVersions.isEmpty()) return null;

        // 按从新到旧排序
        java.util.List<String> sorted = new java.util.ArrayList<>(allVersions);
        sorted.sort((a, b) -> {
            int[] va = parseVersion(a);
            int[] vb = parseVersion(b);
            for (int i = 0; i < 5; i++) {
                if (va[i] != vb[i]) return vb[i] - va[i]; // 降序
            }
            return 0;
        });

        java.util.List<String> newer = new java.util.ArrayList<>();
        java.util.List<String> older = new java.util.ArrayList<>();

        boolean foundCurrent = false;
        for (String v : sorted) {
            String newest = getNewestVersion(currentVer, v);
            if (newest.equals(v) && !v.equals(currentVer)) {
                // v 比 currentVer 更新
                newer.add(v);
            } else {
                older.add(v);
            }
        }

        return new String[][]{
            newer.toArray(new String[0]),
            older.toArray(new String[0])
        };
    }

    private static int parseIntSafe(String s) {
        try { return Integer.parseInt(s); } catch (NumberFormatException e) { return 0; }
    }
}
