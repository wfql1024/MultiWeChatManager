/**
 * icons.js — Inline SVG icons for navigation sidebar.
 * Each icon is a 20x20 SVG with stroke="currentColor" to inherit text color.
 */
var JFC = window.JFC || {};
JFC.icons = {
    login:
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<circle cx="12" cy="8" r="4"/><path d="M20 21a8 8 0 1 0-16 0"/>' +
        '</svg>',

    manage:
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>' +
        '</svg>',

    statistics:
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/>' +
        '</svg>',

    settings:
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<circle cx="12" cy="12" r="3"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72 1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>' +
        '</svg>'
};

/** Apply SVG icons to nav sidebar items */
JFC.icons.applyToNav = function() {
    var iconMap = {
        'login': this.login,
        'manage': this.manage,
        'statistics': this.statistics,
        'settings': this.settings
    };

    var items = document.querySelectorAll('#nav-sidebar .nav-item');
    items.forEach(function(item) {
        var page = item.getAttribute('data-page');
        var iconSpan = item.querySelector('.nav-icon');
        if (iconSpan && iconMap[page]) {
            iconSpan.innerHTML = iconMap[page];
        }
    });
};
