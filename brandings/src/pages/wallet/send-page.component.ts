import { ChangeDetectionStrategy, ChangeDetectorRef, Component, NgZone, OnDestroy, OnInit } from '@angular/core';
import { select, Store } from '@ngrx/store';
import { TranslateService } from '@ngx-translate/core';
import { AlertController, ModalController } from 'ionic-angular';
import { Observable } from 'rxjs/Observable';
import { filter } from 'rxjs/operators';
import { Subscription } from 'rxjs/Subscription';
import { GetAddresssAction, ScanQrCodeAction } from '../../actions';
import { IAppState } from '../../app/app.state';
import {
  ADDRESS_LENGTH,
  CreateSignatureData,
  CreateTransactionResult,
  CURRENCY_TFT,
  KEY_NAME,
  RIVINE_ALGORITHM,
} from '../../interfaces/wallet';
import { CryptoAddress, QrCodeScannedContent } from '../../manual_typings/rogerthat';
import { getAddress, getQrCodeContent } from '../../state/rogerthat.state';
import { parseQuery } from '../../util/rpc';
import { ConfirmSendPageComponent } from './confirm-send-page.component';

const PRECISION = 5;
const DEFAULT_FORM_DATA = {
  amount: 0,
  precision: PRECISION,
  from_address: '',
  to_address: '',
};

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-content>
      <send [data]="data"
            [address]="address$ | async"
            [addressLength]="addressLength"
            (scanQr)="onScanQr()"
            (createSignatureData)="onCreateSignatureData($event)"></send>
    </ion-content>`,
})
export class SendPageComponent implements OnInit, OnDestroy {
  address$: Observable<CryptoAddress>;
  addressLength = ADDRESS_LENGTH;
  data: CreateSignatureData = DEFAULT_FORM_DATA; // cant get it to work with a subject

  private _qrCodeContentSubscription: Subscription;

  constructor(private store: Store<IAppState>,
              private modalCtrl: ModalController,
              private alertCtrl: AlertController,
              private translate: TranslateService,
              private cdRef: ChangeDetectorRef,
              private ngZone: NgZone) {
  }

  ngOnInit() {
    this.store.dispatch(new GetAddresssAction({
      algorithm: RIVINE_ALGORITHM,
      index: 0,
      keyName: KEY_NAME,
      message: this.translate.instant('please_enter_your_pin'),
    }));
    this.address$ = <Observable<CryptoAddress>>this.store.pipe(select(getAddress), filter(a => a !== null));
    this._qrCodeContentSubscription = this.store.pipe(
      select(getQrCodeContent),
      filter(r => r !== null && r.status === 'resolved'),
    ).subscribe((result: QrCodeScannedContent) => {
      const parsedQr = this.parseQr(result.content);
      if (parsedQr.token === CURRENCY_TFT && parsedQr.address) {
        this.setData({ ...this.data, amount: parsedQr.amount, to_address: parsedQr.address });
      } else {
        this.alertCtrl.create({
          message: this.translate.instant('unknown_qr_code_scanned'),
          buttons: [ { text: this.translate.instant('ok') } ],
        }).present();
      }
    });
  }

  ngOnDestroy() {
    this._qrCodeContentSubscription.unsubscribe();
  }

  parseQr(qr: string) {
    let token = CURRENCY_TFT;
    let address = null;
    const [ url, qry ] = qr.split('?');
    const amount = parseFloat(parseQuery(qry || '').amount) || 0;
    const splitUrl = url.split(':');
    for (const part of splitUrl) {
      if (part.length === 3) {
        token = part.toUpperCase();
      }
      if (part.length === ADDRESS_LENGTH) {
        address = part;
      }
    }
    return { token, address, amount };
  }

  onCreateSignatureData(data: CreateSignatureData) {
    // for some fucking reason this does not run in ngZone leading to UI not updating
    this.ngZone.run(() => {
      const modal = this.modalCtrl.create(ConfirmSendPageComponent, {
        transactionData: {
          ...data,
          amount: Math.round(data.amount * Math.pow(10, PRECISION)),
        },
      });
      modal.onDidDismiss((transaction: CreateTransactionResult | null) => {
        if (transaction) {
          const config = {
            title: this.translate.instant('transaction_complete'),
            message: this.translate.instant('transaction_complete_message'),
            buttons: [ { text: this.translate.instant('ok') } ],
          };
          this.alertCtrl.create(config).present();
          this.setData(DEFAULT_FORM_DATA);
        }
      });
      modal.present();
    });
  }

  setData(data: CreateSignatureData) {
    this.data = data;
    this.cdRef.detectChanges();
  }

  onScanQr() {
    this.store.dispatch(new ScanQrCodeAction('front'));
  }
}
