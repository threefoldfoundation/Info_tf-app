import { ChangeDetectionStrategy, Component, OnInit } from '@angular/core';
import { select, Store } from '@ngrx/store';
import { TranslateService } from '@ngx-translate/core';
import { NavParams, ToastController, ViewController } from 'ionic-angular';
import { Observable } from 'rxjs/Observable';
import { filter, map, startWith } from 'rxjs/operators';
import { GetLatestBlockAction } from '../../actions';
import { ParsedTransaction, TfChainBlock } from '../../interfaces/wallet';
import { AmountPipe } from '../../pipes/amount.pipe';
import { getLatestBlock, IBrandingState } from '../../state/app.state';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: 'transaction-detail-page.component.html',
})
export class TransactionDetailPageComponent implements OnInit {
  transaction: ParsedTransaction;
  latestBlock$: Observable<TfChainBlock>;
  confirmations$: Observable<number>;

  constructor(private params: NavParams,
              private translate: TranslateService,
              private amountPipe: AmountPipe,
              private viewCtrl: ViewController,
              private toastCtrl: ToastController,
              private store: Store<IBrandingState>) {
  }

  ngOnInit() {
    this.transaction = this.params.get('transaction');
    this.store.dispatch(new GetLatestBlockAction());
    this.latestBlock$ = <Observable<TfChainBlock>>this.store.pipe(
      select(getLatestBlock),
      filter(b => b !== null),
    );
    this.confirmations$ = this.latestBlock$.pipe(
      startWith({ height: 0 }),
      map(block => block.height - this.transaction.height),
    );
  }

  getAmount(amount: number) {
    return this.amountPipe.transform(Math.abs(amount));
  }

  showCopiedToast(result: { isSuccess: boolean, content?: string }) {
    if (result.isSuccess) {
      this.toastCtrl.create({
        message: this.translate.instant('address_copied_to_clipboard'),
        duration: 3000,
        position: 'bottom',
        showCloseButton: true,
        closeButtonText: this.translate.instant('ok'),
      }).present();
    }
  }

  dismiss() {
    this.viewCtrl.dismiss();
  }
}
