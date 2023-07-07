odoo.define("erplibre_website_snippets_jitsi.dialog", function (require) {
    "use strict";

    var ajax = require("web.ajax");
    var core = require("web.core");
    var widget = require("web_editor.widget");
    var _t = core._t;
    var Dialog = widget.Dialog;
    var options = require("web_editor.snippets.options");
    var sAnimation = require("website.content.snippets.animation");
    var rpc = require("web.rpc");
    var weContext = require("web_editor.context");

    let list_rooms = [];

    var result = $.Deferred(),
        _templates_loaded = ajax.loadXML("/erplibre_website_snippets_jitsi/static/src/xml/widgets.xml", core.qweb);

    var ParamsForm = Dialog.extend({
        template: "erplibre_website_snippets_jitsi.ParamsForm",

        /**
         * Store models info before creating widget
         *
         * @param {Object} parent Widget where this dialog is attached
         * @param {Object} options Dialog creation options
         * @param {Object} rooms rooms list
         * @param {String} chosen Prechosen model
         * @returns {Dialog} New Dialog object
         */
        init: function (parent, options, rooms, chosen) {
            this.chosen = chosen;
            this.rooms = rooms;

            var _options = $.extend(
                {},
                {
                    title: _t("Form Settings"),
                    size: "small",
                },
                options
            );
            return this._super(parent, _options);
        },

        /**
         * Save data
         */
        save: function () {
            this.final_data = this.$("#model").val();
            console.log("save: " + this.final_data);

            rpc.query({
                model: "sinerkia_jitsi_meet.jitsi_meet",
                method: "get_channel",
                args: [parseInt(this.final_data)],
            }).then(function (data) {
                if (_.isEmpty(data)) {
                    return;
                }

                var options = {
                    roomName: "Default", // 'PickAnAppropriateMeetingNameHere',
                    width: "100%", // 700,
                    height: 700,
                    parentNode: document.querySelector("#meet"),
                    userInfo: {},
                    invitees_X: [],
                    configOverwrite: {
                        prejoinPageEnabled: false,
                    },
                    onload: (ev) => {
                        const URL = ev.target.src;

                        $("iframe[id^=jitsiConferenceFrame]").each(function () {
                            if ($(this).attr("id") != "jitsiConferenceFrame0") {
                                $(this).remove();
                            }
                        });

                        console.warn("> Jitsi loaded:", URL, ev);
                    },
                };
                options.roomName = data.meetings.roomName;
                options.userInfo = data.userInfo;
                // document.getElementById("message").innerHTML = data.meetings.roomName;
                document.getElementById("message").innerHTML = "Jitsi url: " + data.meetings.url;
                console.log("Jitsi url: " + data.meetings.url);

                const jitsi = new JitsiMeetExternalAPI(data.meetings.domaineName, options);
                jitsi.addEventListener("incomingMessage", (ev) => console.warn("> Incoming:", ev));
                jitsi.addEventListener("outgoingMessage", (ev) => console.warn("> Outgoing:", ev));
            });

            //
            // var def = this._rpc({
            //     route: '/website_jitsi/get_info/', params: {
            //         jitsi_id: parseInt(this.final_data),
            //     },
            // }).then(function (data) {
            //     if (data.error) {
            //         return;
            //     }
            //
            //     if (_.isEmpty(data)) {
            //         return;
            //     }
            //     options.roomName = data.meetings.roomName;
            //     options.userInfo = data.userInfo;
            //     // document.getElementById("message").innerHTML = data.meetings.roomName;
            //     document.getElementById("message").innerHTML = "Jitsi url: " + data.meetings.url;
            //     console.log("Jitsi url: " + data.meetings.url);
            //
            //     const jitsi = new JitsiMeetExternalAPI(data.meetings.domaineName, options);
            //     jitsi.addEventListener('incomingMessage', ev => console.warn('> Incoming:', ev));
            //     jitsi.addEventListener('outgoingMessage', ev => console.warn('> Outgoing:', ev));
            // });

            // this._rpc({
            //     model: 'ir.model',
            //     method: 'search_read',
            //     kwargs: {domain: [
            //         ["website_form_access", "=", true],
            //     ],
            //     fields: [
            //         "name",
            //         "model",
            //         "website_form_label",
            //     ],
            //     order: [{name: 'website_form_label', asc: true}],
            //     context: weContext.get()},
            // }).done(function (models_list) {
            //     _models_def.resolve(_.indexBy(models_list, "model"));
            // });
            this._super.apply(this, arguments);
        },
    });

    _templates_loaded.done(function () {
        result.resolve({
            ParamsForm: ParamsForm,
        });
    });

    var Form = options.Class.extend({
        init: function () {
            this._super.apply(this, arguments);
            //this.$form = this.$(".website_jitsi");
        },

        /**
         * Ask for a model or remove snippet.
         */
        onBuilt: function () {
            var dialog = new ParamsForm($(".website_jitsi"), {}, list_rooms, "");
            this._super.apply(this, arguments);
            dialog.open();
        },
    });

    let jitsi = (sAnimation.registry.website_jitsi = sAnimation.Class.extend({
        selector: ".website_jitsi",

        /**
         * @override
         */
        start: function () {
            let def = this._rpc({
                model: "sinerkia_jitsi_meet.jitsi_meet",
                method: "search_read",
                kwargs: {
                    fields: ["name", "roomName", "domaineName", "url", "id"],
                    context: weContext.get(),
                },
            }).done(function (models_list) {
                console.log("in rpc " + JSON.stringify(models_list));
                list_rooms = models_list;
                //_models_def.resolve(_.indexBy(models_list, "model"));
            });

            // let def = this._rpc({
            //     route: '/website_jitsi/get_canal_list/'
            // }).then(function (data) {
            //     console.log("in rpc " + JSON.stringify(data));
            //
            //     if (data.error) {
            //         return;
            //     }
            //
            //     if (_.isEmpty(data)) {
            //         return;
            //     }
            //     list_rooms = data;
            //
            //     for (let i = 0; i < data.length; i++) {
            //         //options.roomName = data[i].meetings.roomName;
            //         options.userInfo = data[i]["id"];
            //
            //         //console.log("id: " + data[i]["url"]);
            //
            //         //console.log("Jitsi url: " + data.meetings.url);
            //         //console.log("room name: " + options.roomName);
            //     }
            //
            // });

            return $.when(this._super.apply(this, arguments), def);
        },
    }));

    $(document).on("click", "#channel", function (ev) {
        let optionsDialog = new ParamsForm($(".website_jitsi"), {}, list_rooms, "");
        optionsDialog.open();
    });

    options.registry.erplibre_website_snippets_jitsi_form = Form;
});
