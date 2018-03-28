import { ChangeDetectionStrategy, Component, OnInit } from '@angular/core';
import { Platform } from 'ionic-angular';
import { SendPageComponent } from './index';
import { ReceivePageComponent } from './receive-page.component';
import { TransactionsListPageComponent } from './transactions-list-page.component';

export interface TabPage {
  component: any;
  title: string;
}

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: 'wallet-page.component.html',
})
export class WalletPageComponent implements OnInit {
  tabs: TabPage[];

  constructor(private platform: Platform) {
  }

  ngOnInit() {
    this.tabs = [ {
      component: SendPageComponent,
      title: 'send',
    }, {
      component: TransactionsListPageComponent,
      title: 'transactions',
    }, {
      component: ReceivePageComponent,
      title: 'receive',
    } ];
  }

  close() {
    this.platform.exitApp();
  }
}
