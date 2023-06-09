odoo.define("website_jitsi", function (require) {
    "use strict";
    var sAnimation = require("website.content.snippets.animation");
    sAnimation.registry.website_jitsi = sAnimation.Class.extend({
        selector: ".website_jitsi",

        /**
         * @override
         */
        start: function () {
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
                    //document.body.classList.add('jitsi-loaded');
                },
            };

            let new_record = true;
            let jitsi_id = 0;

            // let new_record = false;
            // let jitsi_id = 1;

            var def = this._rpc({
                route: "/website_jitsi/get_info/",
                params: {
                    new_record: new_record,
                    jitsi_id: jitsi_id,
                },
            }).then(function (data) {
                if (data.error) {
                    return;
                }

                if (_.isEmpty(data)) {
                    return;
                }
                options.roomName = data.meetings.roomName;
                options.userInfo = data.userInfo;
                // document.getElementById("message").innerHTML = data.meetings.roomName;
                document.getElementById("message").innerHTML = "Jitsi url: " + data.meetings.url;
                console.log("Jitsi url: " + data.meetings.url);

                const jitsi = new JitsiMeetExternalAPI(data.meetings.domaineName, options);
                jitsi.addEventListener("incomingMessage", (ev) => console.warn("> Incoming:", ev));
                jitsi.addEventListener("outgoingMessage", (ev) => console.warn("> Outgoing:", ev));
            });
            return $.when(this._super.apply(this, arguments), def);
        },
    });
});
