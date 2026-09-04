/** @odoo-module **/
import {Component} from "@odoo/owl"; import {registry} from "@web/core/registry"; import {useService} from "@web/core/utils/hooks";
class VetQuickCreate extends Component {static template="vet_completion.QuickCreate"; setup(){this.action=useService("action");} open(xmlid,context={}){this.action.doAction(xmlid,{additionalContext:context});}}
registry.category("systray").add("VetCairnQuickCreate",{Component:VetQuickCreate},{sequence:15});
