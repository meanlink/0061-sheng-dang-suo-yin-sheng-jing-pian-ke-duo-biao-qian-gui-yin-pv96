import {mount} from './base.js';
import {render as archive} from './archive_page.js';
import {render as clips} from './clips_page.js';
import {render as labels} from './labels_page.js';
import {render as catalog} from './catalog_page.js';
const pages = {"archive": "声档卷宗", "clips": "片刻证据", "labels": "候选归因", "catalog": "归档检索"};
const screens = {archive, clips, labels, catalog};
mount({title: "声档索引 · 声景片刻的多标签归因", kicker: "东栈声档 / 匿名片刻索引", pages, render: (page, outlet, user) => screens[page](outlet, user)});
